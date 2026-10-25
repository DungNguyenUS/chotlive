from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def gen_uuid() -> str:
    return str(uuid.uuid4())


class ShopRole(str, Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    STAFF = "STAFF"


class SourcePlatform(str, Enum):
    FACEBOOK_PAGE = "FACEBOOK_PAGE"
    FACEBOOK_PERSONAL = "FACEBOOK_PERSONAL"
    DEMO = "DEMO"


class ConnectionStatus(str, Enum):
    DEMO = "DEMO"
    CONNECTED = "CONNECTED"
    NEEDS_PERMISSION = "NEEDS_PERMISSION"
    MANUAL_MODE = "MANUAL_MODE"
    FAILED = "FAILED"
    MISSING_CREDENTIALS = "MISSING_CREDENTIALS"


class LiveSessionStatus(str, Enum):
    LIVE = "LIVE"
    ENDED = "ENDED"


class CommentStatus(str, Enum):
    NEW = "NEW"
    PARSED = "PARSED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    CONFIRMED = "CONFIRMED"
    IGNORED = "IGNORED"
    FAILED = "FAILED"


class OrderStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"
    CANCELLED = "CANCELLED"


class MessageStatus(str, Enum):
    QUEUED = "QUEUED"
    SENDING = "SENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    NEEDS_MANUAL_ACTION = "NEEDS_MANUAL_ACTION"


class PrintJobStatus(str, Enum):
    QUEUED = "QUEUED"
    PRINTING = "PRINTING"
    PRINTED = "PRINTED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class SttResetRule(str, Enum):
    DAILY = "DAILY"
    SESSION = "SESSION"
    NEVER = "NEVER"


DEFAULT_MESSAGE_TEMPLATE = (
    "Chào chị {{customer_name}}! Shop đã ghi nhận chị chốt {{product_name}}.\n"
    "Mã đơn: {{order_code}}\n"
    "Số lượng: {{quantity}}\n"
    "Giá bán: {{unit_price}}\n"
    "Tổng tiền sản phẩm: {{subtotal}}\n"
    "Cảm ơn chị đã ủng hộ shop!"
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    memberships: Mapped[List["ShopMember"]] = relationship("ShopMember", back_populates="user")


class Shop(Base):
    __tablename__ = "shops"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    logo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    stt_reset_rule: Mapped[str] = mapped_column(String(30), default=SttResetRule.DAILY.value, nullable=False)
    current_stt_counter: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_stt_reset_date: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    auto_print_on_confirm: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    confirm_before_print: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    print_paper_size: Mapped[str] = mapped_column(String(20), default="80mm", nullable=False)
    inventory_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    message_template: Mapped[str] = mapped_column(Text, default=DEFAULT_MESSAGE_TEMPLATE, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    members: Mapped[List["ShopMember"]] = relationship("ShopMember", back_populates="shop")
    notification_setting: Mapped[Optional["NotificationSetting"]] = relationship(
        "NotificationSetting", back_populates="shop", uselist=False
    )


class ShopMember(Base):
    __tablename__ = "shop_members"
    __table_args__ = (
        UniqueConstraint("shop_id", "user_id", name="uq_shop_member_shop_user"),
        Index("ix_shop_members_shop_id", "shop_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    shop_id: Mapped[str] = mapped_column(String(36), ForeignKey("shops.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(30), default=ShopRole.STAFF.value, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    shop: Mapped["Shop"] = relationship("Shop", back_populates="members")
    user: Mapped["User"] = relationship("User", back_populates="memberships")


class ConnectedAccount(Base):
    __tablename__ = "connected_accounts"
    __table_args__ = (
        UniqueConstraint("shop_id", "platform", "external_id", name="uq_connected_account_shop_ext"),
        Index("ix_connected_accounts_shop_id", "shop_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    shop_id: Mapped[str] = mapped_column(String(36), ForeignKey("shops.id", ondelete="CASCADE"), nullable=False)
    platform: Mapped[str] = mapped_column(String(40), nullable=False)  # FACEBOOK_PAGE | FACEBOOK_PERSONAL | DEMO
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    connection_status: Mapped[str] = mapped_column(
        String(40), default=ConnectionStatus.MANUAL_MODE.value, nullable=False
    )
    encrypted_access_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    granted_permissions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # comma-separated
    missing_permissions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # comma-separated
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class LiveSession(Base):
    __tablename__ = "live_sessions"
    __table_args__ = (Index("ix_live_sessions_shop_id", "shop_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    shop_id: Mapped[str] = mapped_column(String(36), ForeignKey("shops.id", ondelete="CASCADE"), nullable=False)
    connected_account_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("connected_accounts.id", ondelete="SET NULL"), nullable=True
    )
    external_video_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)  # FACEBOOK_PAGE | FACEBOOK_PERSONAL | DEMO
    connection_mode: Mapped[str] = mapped_column(
        String(40), default=ConnectionStatus.MANUAL_MODE.value, nullable=False
    )
    status: Mapped[str] = mapped_column(String(30), default=LiveSessionStatus.LIVE.value, nullable=False)
    session_stt_counter: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("shop_id", "code", name="uq_product_shop_code"),
        Index("ix_products_shop_code", "shop_id", "code"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    shop_id: Mapped[str] = mapped_column(String(36), ForeignKey("shops.id", ondelete="CASCADE"), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    track_inventory: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    stock_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    variants: Mapped[List["ProductVariant"]] = relationship(
        "ProductVariant", back_populates="product", cascade="all, delete-orphan"
    )


class ProductVariant(Base):
    __tablename__ = "product_variants"
    __table_args__ = (Index("ix_product_variants_product_id", "product_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    shop_id: Mapped[str] = mapped_column(String(36), ForeignKey("shops.id", ondelete="CASCADE"), nullable=False)
    sku: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    size: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    price_override: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    stock_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    product: Mapped["Product"] = relationship("Product", back_populates="variants")


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (Index("ix_customers_shop_id", "shop_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    shop_id: Mapped[str] = mapped_column(String(36), ForeignKey("shops.id", ondelete="CASCADE"), nullable=False)
    platform_user_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    source_type: Mapped[str] = mapped_column(String(40), default=SourcePlatform.FACEBOOK_PAGE.value, nullable=False)
    customer_stt: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class Comment(Base):
    __tablename__ = "comments"
    __table_args__ = (
        UniqueConstraint("shop_id", "external_comment_id", name="uq_comment_shop_ext_comment_id"),
        Index("ix_comments_shop_session_time", "shop_id", "live_session_id", "commented_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    shop_id: Mapped[str] = mapped_column(String(36), ForeignKey("shops.id", ondelete="CASCADE"), nullable=False)
    live_session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("live_sessions.id", ondelete="CASCADE"), nullable=False
    )
    customer_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("customers.id", ondelete="SET NULL"), nullable=True
    )

    source_type: Mapped[str] = mapped_column(String(40), nullable=False)  # FACEBOOK_PAGE | FACEBOOK_PERSONAL | DEMO
    connection_mode: Mapped[str] = mapped_column(
        String(40), default=ConnectionStatus.MANUAL_MODE.value, nullable=False
    )
    external_page_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    external_live_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    external_comment_id: Mapped[str] = mapped_column(String(160), nullable=False)
    commenter_external_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    commenter_name: Mapped[str] = mapped_column(String(255), nullable=False)
    commenter_avatar: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    raw_message: Mapped[str] = mapped_column(Text, nullable=False)

    parsed_product_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    parsed_quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    parsed_color: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    parsed_size: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    parsed_intent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    parse_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    missing_fields: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_ambiguous: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    status: Mapped[str] = mapped_column(String(30), default=CommentStatus.NEW.value, nullable=False, index=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    commented_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("shop_id", "order_code", name="uq_order_shop_order_code"),
        UniqueConstraint("shop_id", "comment_id", name="uq_order_shop_comment_id"),
        UniqueConstraint("shop_id", "idempotency_key", name="uq_order_shop_idempotency_key"),
        Index("ix_orders_shop_created", "shop_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    shop_id: Mapped[str] = mapped_column(String(36), ForeignKey("shops.id", ondelete="CASCADE"), nullable=False)
    live_session_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("live_sessions.id", ondelete="SET NULL"), nullable=True
    )
    comment_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("comments.id", ondelete="RESTRICT"), nullable=True
    )
    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    confirmed_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    order_code: Mapped[str] = mapped_column(String(64), nullable=False)
    customer_stt: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default=OrderStatus.CONFIRMED.value, nullable=False, index=True)
    subtotal: Mapped[float] = mapped_column(Float, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)

    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    items: Mapped[List["OrderItem"]] = relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan"
    )
    message_logs: Mapped[List["MessageLog"]] = relationship("MessageLog", back_populates="order")
    print_jobs: Mapped[List["PrintJob"]] = relationship("PrintJob", back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (Index("ix_order_items_order_id", "order_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    shop_id: Mapped[str] = mapped_column(String(36), ForeignKey("shops.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    variant_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True
    )

    product_code_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    product_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    variant_snapshot: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_snapshot: Mapped[float] = mapped_column(Float, nullable=False)
    line_total: Mapped[float] = mapped_column(Float, nullable=False)

    order: Mapped["Order"] = relationship("Order", back_populates="items")


class MessageLog(Base):
    __tablename__ = "message_logs"
    __table_args__ = (Index("ix_message_logs_shop_order", "shop_id", "order_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    shop_id: Mapped[str] = mapped_column(String(36), ForeignKey("shops.id", ondelete="CASCADE"), nullable=False)
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    comment_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("comments.id", ondelete="SET NULL"), nullable=True
    )

    provider_mode: Mapped[str] = mapped_column(String(40), nullable=False)  # MOCK | META_GRAPH_API | MANUAL
    external_message_id: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    rendered_content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default=MessageStatus.QUEUED.value, nullable=False, index=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    error_code: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    error_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    messenger_thread_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    order: Mapped["Order"] = relationship("Order", back_populates="message_logs")


class PrintJob(Base):
    __tablename__ = "print_jobs"
    __table_args__ = (Index("ix_print_jobs_shop_order", "shop_id", "order_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    shop_id: Mapped[str] = mapped_column(String(36), ForeignKey("shops.id", ondelete="CASCADE"), nullable=False)
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)

    print_mode: Mapped[str] = mapped_column(String(30), default="BROWSER", nullable=False)  # BROWSER | PRINT_BRIDGE
    paper_size: Mapped[str] = mapped_column(String(20), default="80mm", nullable=False)  # 80mm | A6 | A5
    status: Mapped[str] = mapped_column(String(30), default=PrintJobStatus.QUEUED.value, nullable=False, index=True)
    snapshot_payload: Mapped[str] = mapped_column(Text, nullable=False)  # JSON snapshot
    rendered_html: Mapped[str] = mapped_column(Text, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    printed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    order: Mapped["Order"] = relationship("Order", back_populates="print_jobs")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_shop_created", "shop_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    shop_id: Mapped[str] = mapped_column(String(36), ForeignKey("shops.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    __table_args__ = (
        UniqueConstraint("external_event_id", name="uq_webhook_external_event_id"),
        Index("ix_webhook_events_shop_id", "shop_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    shop_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("shops.id", ondelete="SET NULL"), nullable=True
    )
    external_event_id: Mapped[str] = mapped_column(String(180), nullable=False)
    object_type: Mapped[str] = mapped_column(String(60), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_payload: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="RECEIVED", nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class NotificationSetting(Base):
    __tablename__ = "notification_settings"
    __table_args__ = (UniqueConstraint("shop_id", name="uq_notification_settings_shop_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    shop_id: Mapped[str] = mapped_column(String(36), ForeignKey("shops.id", ondelete="CASCADE"), nullable=False)
    font_family: Mapped[str] = mapped_column(String(80), default="Inter, Arial, sans-serif", nullable=False)
    font_size_px: Mapped[int] = mapped_column(Integer, default=13, nullable=False)
    margin_mm: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    header_note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    footer_note: Mapped[Optional[str]] = mapped_column(
        String(255), default="Cảm ơn quý khách đã mua hàng trên livestream!", nullable=True
    )
    enable_auto_messenger: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    messenger_template: Mapped[str] = mapped_column(Text, default=DEFAULT_MESSAGE_TEMPLATE, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    shop: Mapped["Shop"] = relationship("Shop", back_populates="notification_setting")
