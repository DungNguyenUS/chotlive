from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Protocol

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decrypt_secret
from app.models import (
    Comment,
    ConnectedAccount,
    ConnectionStatus,
    Customer,
    MessageLog,
    MessageStatus,
    Order,
    OrderItem,
    Shop,
    SourcePlatform,
)


REQUIRED_PAGE_PERMISSIONS = {"pages_show_list", "pages_read_engagement", "pages_messaging"}


@dataclass
class PrivateReplyDispatchResult:
    provider_mode: str  # MOCK | META_GRAPH_API | MANUAL
    status: str  # SENT | FAILED | NEEDS_MANUAL_ACTION
    external_message_id: Optional[str] = None
    error_code: Optional[str] = None
    error_reason: Optional[str] = None
    is_retryable: bool = False
    retry_attempts_used: int = 0


class MetaMessengerAdapter(Protocol):
    def send_private_reply(
        self,
        page_id: str,
        comment_id: str,
        message_text: str,
        access_token: Optional[str] = None,
    ) -> PrivateReplyDispatchResult:
        ...


class MockMetaMessengerAdapter:
    """
    Transparent Mock Adapter for local development and automated testing.
    Never claims to be a real Meta connection: sets provider_mode='MOCK'.
    Supports deterministic simulation triggers via message/comment markers for QA tests.
    """

    def send_private_reply(
        self,
        page_id: str,
        comment_id: str,
        message_text: str,
        access_token: Optional[str] = None,
    ) -> PrivateReplyDispatchResult:
        if "SIMULATE_MISSING_PERMISSION" in comment_id:
            return PrivateReplyDispatchResult(
                provider_mode="MOCK",
                status=MessageStatus.NEEDS_MANUAL_ACTION.value,
                error_code="PERMISSION_DENIED_200",
                error_reason="Thiếu quyền pages_messaging trên Fanpage để gửi Private Reply.",
                is_retryable=False,
            )
        if "SIMULATE_AMBIGUOUS_TIMEOUT" in comment_id:
            return PrivateReplyDispatchResult(
                provider_mode="MOCK",
                status=MessageStatus.NEEDS_MANUAL_ACTION.value,
                error_code="AMBIGUOUS_WRITE_TIMEOUT",
                error_reason=(
                    "Quá thời gian chờ phản hồi từ API sau khi gửi request. "
                    "Không tự động gửi lại để tránh gửi tin nhắn trùng cho khách."
                ),
                is_retryable=False,
            )
        if "SIMULATE_TRANSIENT_503" in comment_id:
            return PrivateReplyDispatchResult(
                provider_mode="MOCK",
                status=MessageStatus.FAILED.value,
                error_code="HTTP_503_TEMPORARY",
                error_reason="Máy chủ Meta tạm thời quá tải (Simulated 503).",
                is_retryable=True,
            )
        if "SIMULATE_PERMANENT_ERROR" in comment_id:
            return PrivateReplyDispatchResult(
                provider_mode="MOCK",
                status=MessageStatus.FAILED.value,
                error_code="META_ERR_10900",
                error_reason="Bình luận này đã được phản hồi Private Reply trước đó.",
                is_retryable=False,
            )

        return PrivateReplyDispatchResult(
            provider_mode="MOCK",
            status=MessageStatus.SENT.value,
            external_message_id=f"mock_mid.{uuid.uuid4().hex[:16]}",
            is_retryable=False,
        )


class RealMetaGraphMessengerAdapter:
    """
    Official Meta Graph API Private Replies Adapter.
    Ref: https://developers.facebook.com/docs/messenger-platform/discovery/private-replies/
    Endpoint: POST https://graph.facebook.com/{META_API_VERSION}/{PAGE-ID}/messages
    Body: {"recipient": {"comment_id": "<COMMENT_ID>"}, "message": {"text": "<TEXT>"}}
    """

    def __init__(self, timeout_seconds: float = 10.0) -> None:
        self.timeout_seconds = timeout_seconds

    def send_private_reply(
        self,
        page_id: str,
        comment_id: str,
        message_text: str,
        access_token: Optional[str] = None,
    ) -> PrivateReplyDispatchResult:
        if not access_token:
            if not settings.has_real_meta_credentials:
                return PrivateReplyDispatchResult(
                    provider_mode="META_GRAPH_API",
                    status=MessageStatus.NEEDS_MANUAL_ACTION.value,
                    error_code="MISSING_META_CREDENTIALS",
                    error_reason=(
                        "BLOCKED: Chưa cấu hình META_APP_ID / META_APP_SECRET hoặc Page Access Token. "
                        "Vui lòng nhập Page Access Token hoặc gửi tin nhắn thủ công."
                    ),
                    is_retryable=False,
                )
            return PrivateReplyDispatchResult(
                provider_mode="META_GRAPH_API",
                status=MessageStatus.NEEDS_MANUAL_ACTION.value,
                error_code="MISSING_PAGE_ACCESS_TOKEN",
                error_reason="Fanpage chưa có Page Access Token hợp lệ.",
                is_retryable=False,
            )

        url = f"https://graph.facebook.com/{settings.META_API_VERSION}/{page_id}/messages"
        payload = {
            "recipient": {"comment_id": comment_id},
            "message": {"text": message_text},
        }
        headers = {"Authorization": f"Bearer {access_token}"}

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.post(url, json=payload, headers=headers)
        except httpx.ConnectTimeout:
            return PrivateReplyDispatchResult(
                provider_mode="META_GRAPH_API",
                status=MessageStatus.FAILED.value,
                error_code="CONNECT_TIMEOUT",
                error_reason="Không thể kết nối tới máy chủ Graph API (ConnectTimeout).",
                is_retryable=True,
            )
        except httpx.ReadTimeout:
            # ReadTimeout after sending POST means we do NOT know if Meta processed the Private Reply.
            # Per policy: Never automatically re-send when previous result is indeterminate.
            return PrivateReplyDispatchResult(
                provider_mode="META_GRAPH_API",
                status=MessageStatus.NEEDS_MANUAL_ACTION.value,
                error_code="READ_TIMEOUT_INDETERMINATE",
                error_reason=(
                    "Hết thời gian chờ đọc phản hồi sau khi gửi lệnh tới Meta. "
                    "Trạng thái chưa xác định nên hệ thống dừng tự động gửi lại để tránh trùng lặp."
                ),
                is_retryable=False,
            )
        except Exception as exc:
            return PrivateReplyDispatchResult(
                provider_mode="META_GRAPH_API",
                status=MessageStatus.FAILED.value,
                error_code="NETWORK_ERROR",
                error_reason=f"Lỗi kết nối mạng: {type(exc).__name__}",
                is_retryable=True,
            )

        if resp.status_code == 200:
            data = resp.json()
            return PrivateReplyDispatchResult(
                provider_mode="META_GRAPH_API",
                status=MessageStatus.SENT.value,
                external_message_id=data.get("message_id"),
                is_retryable=False,
            )

        # Parse Meta Graph error structure
        err_code = f"HTTP_{resp.status_code}"
        err_msg = "Lỗi từ Meta Graph API"
        try:
            err_json = resp.json().get("error", {})
            if err_json:
                err_code = f"META_{err_json.get('code', resp.status_code)}_{err_json.get('error_subcode', '')}".rstrip("_")
                err_msg = err_json.get("message", err_msg)
        except Exception:
            pass

        if resp.status_code in {500, 502, 503, 504, 429}:
            return PrivateReplyDispatchResult(
                provider_mode="META_GRAPH_API",
                status=MessageStatus.FAILED.value,
                error_code=err_code,
                error_reason=err_msg,
                is_retryable=True,
            )

        return PrivateReplyDispatchResult(
            provider_mode="META_GRAPH_API",
            status=MessageStatus.NEEDS_MANUAL_ACTION.value,
            error_code=err_code,
            error_reason=err_msg,
            is_retryable=False,
        )


def format_vnd(amount: float) -> str:
    return f"{int(round(amount)):,}".replace(",", ".") + "đ"


def render_order_message(
    template: str,
    customer_name: str,
    product_name: str,
    order_code: str,
    quantity: int,
    unit_price: float,
    subtotal: float,
) -> str:
    """
    Renders the shop's customizable message template without inventing shipping fees or addresses.
    """
    rendered = template
    replacements = {
        "{{customer_name}}": customer_name,
        "{{product_name}}": product_name,
        "{{order_code}}": order_code,
        "{{quantity}}": str(quantity),
        "{{unit_price}}": format_vnd(unit_price),
        "{{subtotal}}": format_vnd(subtotal),
    }
    for key, val in replacements.items():
        rendered = rendered.replace(key, val)
    return rendered


def build_messenger_thread_url(comment: Optional[Comment], customer: Customer) -> Optional[str]:
    ext_user_id = (comment.commenter_external_id if comment else None) or customer.platform_user_id
    if ext_user_id and ext_user_id.strip():
        clean_id = ext_user_id.strip()
        if clean_id.isdigit() or clean_id.startswith("fb_"):
            return f"https://www.facebook.com/messages/t/{clean_id}"
    return None


def dispatch_order_confirmation_message(
    db: Session,
    shop: Shop,
    order: Order,
    first_item: OrderItem,
    customer: Customer,
    comment: Optional[Comment],
    connected_account: Optional[ConnectedAccount] = None,
    adapter_override: Optional[MetaMessengerAdapter] = None,
    sleep_fn=time.sleep,
) -> MessageLog:
    """
    Executes the Private Reply policy checks, renders the confirmation message,
    and dispatches via the appropriate adapter with bounded exponential backoff.
    Never marks a message SENT when only copied/opened or when Personal Profile is used.
    """
    template = shop.message_template
    if shop.notification_setting and shop.notification_setting.messenger_template:
        template = shop.notification_setting.messenger_template

    rendered_text = render_order_message(
        template=template,
        customer_name=customer.display_name,
        product_name=first_item.product_name_snapshot,
        order_code=order.order_code,
        quantity=first_item.quantity,
        unit_price=first_item.unit_price_snapshot,
        subtotal=order.subtotal,
    )
    thread_url = build_messenger_thread_url(comment, customer)

    # Check if comment already has a SENT message log (1 Private Reply per comment rule)
    if comment:
        existing_sent = (
            db.query(MessageLog)
            .filter(
                MessageLog.shop_id == shop.id,
                MessageLog.comment_id == comment.id,
                MessageLog.status == MessageStatus.SENT.value,
            )
            .first()
        )
        if existing_sent:
            return existing_sent

    # Case 1: Personal profile or no comment source -> Official API does not support automated Private Replies
    if not comment or comment.source_type == SourcePlatform.FACEBOOK_PERSONAL.value or comment.connection_mode == ConnectionStatus.MANUAL_MODE.value:
        log = MessageLog(
            shop_id=shop.id,
            order_id=order.id,
            comment_id=comment.id if comment else None,
            provider_mode="MANUAL",
            rendered_content=rendered_text,
            status=MessageStatus.NEEDS_MANUAL_ACTION.value,
            error_code="PERSONAL_PROFILE_NO_OFFICIAL_API",
            error_reason=(
                "Nguồn Facebook Trang Cá Nhân hoặc chế độ Thủ Công không hỗ trợ gửi tin nhắn tự động "
                "qua API chính thức của Meta. Vui lòng sao chép nội dung bên dưới và gửi qua Messenger."
            ),
            messenger_thread_url=thread_url,
        )
        db.add(log)
        db.flush()
        return log

    # Case 2: Check 7-day Private Reply eligibility window
    now = datetime.now(timezone.utc)
    comment_time = comment.commented_at
    if comment_time.tzinfo is None:
        comment_time = comment_time.replace(tzinfo=timezone.utc)
    if now - comment_time > timedelta(days=7):
        log = MessageLog(
            shop_id=shop.id,
            order_id=order.id,
            comment_id=comment.id,
            provider_mode="META_GRAPH_API",
            rendered_content=rendered_text,
            status=MessageStatus.NEEDS_MANUAL_ACTION.value,
            error_code="PRIVATE_REPLY_WINDOW_EXPIRED_7D",
            error_reason="Bình luận đã quá thời hạn 7 ngày theo chính sách Private Replies của Meta.",
            messenger_thread_url=thread_url,
        )
        db.add(log)
        db.flush()
        return log

    # Case 3: Check permissions on ConnectedAccount if available
    if connected_account and connected_account.connection_status == ConnectionStatus.NEEDS_PERMISSION.value:
        log = MessageLog(
            shop_id=shop.id,
            order_id=order.id,
            comment_id=comment.id,
            provider_mode="META_GRAPH_API",
            rendered_content=rendered_text,
            status=MessageStatus.NEEDS_MANUAL_ACTION.value,
            error_code="MISSING_PAGES_MESSAGING_PERMISSION",
            error_reason=f"Fanpage thiếu quyền bắt buộc: {connected_account.missing_permissions or 'pages_messaging'}.",
            messenger_thread_url=thread_url,
        )
        db.add(log)
        db.flush()
        return log

    # Select adapter
    if adapter_override is not None:
        adapter = adapter_override
    elif comment.source_type == SourcePlatform.DEMO.value or comment.connection_mode == ConnectionStatus.DEMO.value:
        if not settings.allow_mock_provider:
            log = MessageLog(
                shop_id=shop.id,
                order_id=order.id,
                comment_id=comment.id,
                provider_mode="META_GRAPH_API",
                rendered_content=rendered_text,
                status=MessageStatus.NEEDS_MANUAL_ACTION.value,
                error_code="MOCK_DISABLED_IN_PRODUCTION",
                error_reason="Chế độ Mock bị khóa trong môi trường Production.",
                messenger_thread_url=thread_url,
            )
            db.add(log)
            db.flush()
            return log
        adapter = MockMetaMessengerAdapter()
    else:
        adapter = RealMetaGraphMessengerAdapter()

    access_token: Optional[str] = None
    if connected_account and connected_account.encrypted_access_token:
        access_token = decrypt_secret(connected_account.encrypted_access_token)

    page_id = comment.external_page_id or (connected_account.external_id if connected_account else "demo_page")

    log = MessageLog(
        shop_id=shop.id,
        order_id=order.id,
        comment_id=comment.id,
        provider_mode="MOCK" if isinstance(adapter, MockMetaMessengerAdapter) else "META_GRAPH_API",
        rendered_content=rendered_text,
        status=MessageStatus.SENDING.value,
        retry_count=0,
        max_retries=3,
        messenger_thread_url=thread_url,
    )
    db.add(log)
    db.flush()

    max_retries = log.max_retries
    attempt = 0
    while True:
        result = adapter.send_private_reply(
            page_id=page_id,
            comment_id=comment.external_comment_id,
            message_text=rendered_text,
            access_token=access_token,
        )
        log.provider_mode = result.provider_mode
        if result.status == MessageStatus.SENT.value:
            log.status = MessageStatus.SENT.value
            log.external_message_id = result.external_message_id
            log.error_code = None
            log.error_reason = None
            log.sent_at = datetime.now(timezone.utc)
            break

        log.error_code = result.error_code
        log.error_reason = result.error_reason

        if not result.is_retryable or attempt >= max_retries:
            log.status = result.status
            break

        attempt += 1
        log.retry_count = attempt
        backoff_sec = min(0.05 * (2 ** (attempt - 1)), 0.5)
        sleep_fn(backoff_sec)

    db.flush()
    return log
