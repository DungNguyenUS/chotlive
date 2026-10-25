from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    Comment,
    CommentStatus,
    ConnectedAccount,
    Customer,
    LiveSession,
    Order,
    OrderItem,
    OrderStatus,
    Product,
    ProductVariant,
    Shop,
    SttResetRule,
    User,
)
from app.schemas import ConfirmOrderFromCommentRequest, ConfirmOrderWorkflowResponse, OrderResponse
from app.services.comment_parser import parse_livestream_comment
from app.services.meta_service import MetaMessengerAdapter, dispatch_order_confirmation_message
from app.services.print_service import create_and_dispatch_print_job


def _allocate_next_customer_stt(db: Session, shop: Shop, live_session: Optional[LiveSession]) -> int:
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if shop.stt_reset_rule == SttResetRule.SESSION.value and live_session is not None:
        live_session.session_stt_counter = (live_session.session_stt_counter or 0) + 1
        return live_session.session_stt_counter

    if shop.stt_reset_rule == SttResetRule.DAILY.value:
        if shop.last_stt_reset_date != today_str:
            shop.current_stt_counter = 0
            shop.last_stt_reset_date = today_str

    shop.current_stt_counter = (shop.current_stt_counter or 0) + 1
    return shop.current_stt_counter


def _generate_unique_order_code(db: Session, shop_id: str) -> str:
    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    count_for_shop = db.query(Order).filter(Order.shop_id == shop_id).count() + 1
    base_code = f"DH-{date_part}-{count_for_shop:04d}"
    exists = db.query(Order).filter(Order.shop_id == shop_id, Order.order_code == base_code).first()
    if not exists:
        return base_code
    return f"DH-{date_part}-{count_for_shop:04d}-{uuid.uuid4().hex[:4].upper()}"


def confirm_order_from_comment(
    db: Session,
    shop: Shop,
    user: User,
    req: ConfirmOrderFromCommentRequest,
    ip_address: Optional[str] = None,
    messenger_adapter_override: Optional[MetaMessengerAdapter] = None,
) -> ConfirmOrderWorkflowResponse:
    """
    Executes the 13-step "ĐÃ CHỐT" workflow atomically with strict idempotency
    and database unique constraints so concurrent clicks never create duplicate orders.
    """
    # Step 2 & 3: Check if idempotency_key or comment_id already has an order in this shop
    existing_by_key = (
        db.query(Order)
        .filter(Order.shop_id == shop.id, Order.idempotency_key == req.idempotency_key)
        .first()
    )
    if existing_by_key:
        comment_obj = db.query(Comment).filter(Comment.id == existing_by_key.comment_id).first()
        return ConfirmOrderWorkflowResponse(
            order=OrderResponse.model_validate(existing_by_key),
            comment_status=comment_obj.status if comment_obj else CommentStatus.CONFIRMED.value,
            message_log=existing_by_key.message_logs[0] if existing_by_key.message_logs else None,
            print_job=existing_by_key.print_jobs[0] if existing_by_key.print_jobs else None,
            was_idempotent_replay=True,
        )

    comment = (
        db.query(Comment)
        .filter(Comment.id == req.comment_id, Comment.shop_id == shop.id)
        .first()
    )
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy bình luận trong cửa hàng này.",
        )

    existing_by_comment = (
        db.query(Order)
        .filter(Order.shop_id == shop.id, Order.comment_id == comment.id)
        .first()
    )
    if existing_by_comment:
        return ConfirmOrderWorkflowResponse(
            order=OrderResponse.model_validate(existing_by_comment),
            comment_status=comment.status,
            message_log=existing_by_comment.message_logs[0] if existing_by_comment.message_logs else None,
            print_job=existing_by_comment.print_jobs[0] if existing_by_comment.print_jobs else None,
            was_idempotent_replay=True,
        )

    # Step 4: Parse or resolve explicit staff confirmation for product, variant, and quantity
    active_products = (
        db.query(Product)
        .filter(Product.shop_id == shop.id, Product.is_active == True)  # noqa: E712
        .all()
    )
    parse_res = parse_livestream_comment(comment.raw_message, active_products=active_products)

    product: Optional[Product] = None
    if req.product_id:
        product = (
            db.query(Product)
            .filter(Product.id == req.product_id, Product.shop_id == shop.id, Product.is_active == True)  # noqa: E712
            .first()
        )
    elif req.product_code:
        product = (
            db.query(Product)
            .filter(
                Product.shop_id == shop.id,
                Product.code == req.product_code.strip().upper(),
                Product.is_active == True,  # noqa: E712
            )
            .first()
        )
    else:
        # Staff did not explicitly pick a product -> only auto-resolve if parser is unambiguous
        if parse_res.is_ambiguous and not req.force_confirm_ambiguous:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "AMBIGUOUS_COMMENT_REQUIRES_CONFIRMATION",
                    "message": "Bình luận chưa rõ mã hàng hoặc biến thể. Vui lòng chọn xác nhận sản phẩm trước khi chốt.",
                    "parse_result": parse_res.model_dump(),
                },
            )
        if parse_res.matched_product_id:
            product = (
                db.query(Product)
                .filter(Product.id == parse_res.matched_product_id, Product.shop_id == shop.id)
                .first()
            )

    if not product:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "PRODUCT_NOT_FOUND_OR_AMBIGUOUS",
                "message": "Không xác định được sản phẩm hợp lệ trong danh mục của shop. Vui lòng chọn sản phẩm.",
                "parse_result": parse_res.model_dump(),
            },
        )

    quantity = req.quantity if req.quantity is not None else (parse_res.quantity or 1)
    if quantity <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Số lượng phải lớn hơn 0.")

    # Resolve variant and unit price strictly from catalog (never guessed)
    variant: Optional[ProductVariant] = None
    if req.variant_id:
        variant = (
            db.query(ProductVariant)
            .filter(ProductVariant.id == req.variant_id, ProductVariant.product_id == product.id)
            .first()
        )

    unit_price = variant.price_override if (variant and variant.price_override is not None) else product.unit_price
    if unit_price < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Đơn giá sản phẩm không hợp lệ.")

    chosen_color = req.color or (variant.color if variant else None) or parse_res.color
    chosen_size = req.size or (variant.size if variant else None) or parse_res.size
    variant_parts = [p for p in [chosen_color, chosen_size] if p]
    variant_label = " / ".join(variant_parts) if variant_parts else "Mặc định"

    # Inventory check if enabled
    if shop.inventory_enabled or product.track_inventory:
        if product.stock_quantity < quantity:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Sản phẩm {product.code} không đủ tồn kho (Còn {product.stock_quantity}, cần {quantity}).",
            )
        product.stock_quantity -= quantity

    live_session = (
        db.query(LiveSession)
        .filter(LiveSession.id == comment.live_session_id, LiveSession.shop_id == shop.id)
        .first()
    )

    # Resolve or create Customer in shop
    customer: Optional[Customer] = None
    if comment.customer_id:
        customer = db.query(Customer).filter(Customer.id == comment.customer_id, Customer.shop_id == shop.id).first()
    if not customer and comment.commenter_external_id:
        customer = (
            db.query(Customer)
            .filter(
                Customer.shop_id == shop.id,
                Customer.platform_user_id == comment.commenter_external_id,
            )
            .first()
        )
    if not customer:
        customer = Customer(
            shop_id=shop.id,
            platform_user_id=comment.commenter_external_id,
            display_name=comment.commenter_name,
            avatar_url=comment.commenter_avatar,
            source_type=comment.source_type,
        )
        db.add(customer)
        db.flush()

    comment.customer_id = customer.id

    # Step 8 & 9: Allocate unique order_code and customer_stt
    stt_number = customer.customer_stt
    if not stt_number or shop.stt_reset_rule == SttResetRule.SESSION.value:
        stt_number = _allocate_next_customer_stt(db, shop, live_session)
        customer.customer_stt = stt_number

    order_code = _generate_unique_order_code(db, shop.id)
    subtotal = round(unit_price * quantity, 2)

    # Step 7 & 10: Create Order and OrderItem inside database transaction
    order = Order(
        shop_id=shop.id,
        live_session_id=comment.live_session_id,
        comment_id=comment.id,
        customer_id=customer.id,
        confirmed_by_user_id=user.id,
        order_code=order_code,
        customer_stt=stt_number,
        status=OrderStatus.CONFIRMED.value,
        subtotal=subtotal,
        notes=req.notes,
        idempotency_key=req.idempotency_key,
    )
    db.add(order)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        # Concurrent click won the race! Return the existing order idempotently.
        winner = (
            db.query(Order)
            .filter(
                Order.shop_id == shop.id,
                (Order.comment_id == comment.id) | (Order.idempotency_key == req.idempotency_key),
            )
            .first()
        )
        if winner:
            return ConfirmOrderWorkflowResponse(
                order=OrderResponse.model_validate(winner),
                comment_status=CommentStatus.CONFIRMED.value,
                message_log=winner.message_logs[0] if winner.message_logs else None,
                print_job=winner.print_jobs[0] if winner.print_jobs else None,
                was_idempotent_replay=True,
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bình luận này vừa được một nhân viên khác chốt đơn.",
        )

    order_item = OrderItem(
        order_id=order.id,
        shop_id=shop.id,
        product_id=product.id,
        variant_id=variant.id if variant else None,
        product_code_snapshot=product.code,
        product_name_snapshot=product.name,
        variant_snapshot=variant_label,
        quantity=quantity,
        unit_price_snapshot=unit_price,
        line_total=subtotal,
    )
    db.add(order_item)

    comment.status = CommentStatus.CONFIRMED.value
    comment.parsed_product_code = product.code
    comment.parsed_quantity = quantity
    comment.parsed_color = chosen_color
    comment.parsed_size = chosen_size

    # Audit log
    audit = AuditLog(
        shop_id=shop.id,
        user_id=user.id,
        action="ORDER_CONFIRMED",
        entity_type="Order",
        entity_id=order.id,
        details=json.dumps(
            {
                "order_code": order.order_code,
                "comment_id": comment.id,
                "product_code": product.code,
                "quantity": quantity,
                "unit_price": unit_price,
                "subtotal": subtotal,
            },
            ensure_ascii=False,
        ),
        ip_address=ip_address,
    )
    db.add(audit)
    db.commit()
    db.refresh(order)

    # Step 11: Enqueue / dispatch Messenger confirmation (independent of order transaction)
    msg_log = None
    if req.trigger_messenger:
        conn_acc = None
        if live_session and live_session.connected_account_id:
            conn_acc = (
                db.query(ConnectedAccount)
                .filter(ConnectedAccount.id == live_session.connected_account_id)
                .first()
            )
        msg_log = dispatch_order_confirmation_message(
            db=db,
            shop=shop,
            order=order,
            first_item=order_item,
            customer=customer,
            comment=comment,
            connected_account=conn_acc,
            adapter_override=messenger_adapter_override,
        )
        db.commit()
        db.refresh(msg_log)

    # Step 12: Enqueue / dispatch Print Job (independent of order transaction)
    print_job = None
    if req.trigger_print and shop.auto_print_on_confirm:
        print_job = create_and_dispatch_print_job(
            db=db,
            shop=shop,
            order=order,
            customer=customer,
            first_item=order_item,
            comment=comment,
            print_mode=req.print_mode,
            paper_size=shop.print_paper_size,
        )
        db.commit()
        db.refresh(print_job)

    db.refresh(order)
    return ConfirmOrderWorkflowResponse(
        order=OrderResponse.model_validate(order),
        comment_status=comment.status,
        message_log=msg_log,
        print_job=print_job,
        was_idempotent_replay=False,
    )
