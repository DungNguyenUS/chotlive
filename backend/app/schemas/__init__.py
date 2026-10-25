from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# ==============================================================================
# AUTHENTICATION & USERS
# ==============================================================================

class UserRegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255)
    password: str = Field(..., min_length=6, max_length=128)


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ==============================================================================
# SHOPS & MEMBERS
# ==============================================================================

class ShopCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None, max_length=500)
    logo_url: Optional[str] = Field(None, max_length=500)
    stt_reset_rule: str = Field("DAILY", pattern="^(DAILY|SESSION|NEVER)$")
    print_paper_size: str = Field("80mm", pattern="^(80mm|A6|A5)$")
    auto_print_on_confirm: bool = True
    confirm_before_print: bool = True
    inventory_enabled: bool = False


class ShopUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None, max_length=500)
    logo_url: Optional[str] = Field(None, max_length=500)
    stt_reset_rule: Optional[str] = Field(None, pattern="^(DAILY|SESSION|NEVER)$")
    print_paper_size: Optional[str] = Field(None, pattern="^(80mm|A6|A5)$")
    auto_print_on_confirm: Optional[bool] = None
    confirm_before_print: Optional[bool] = None
    inventory_enabled: Optional[bool] = None
    message_template: Optional[str] = Field(None, min_length=10, max_length=2000)


class ShopResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    phone: Optional[str]
    address: Optional[str]
    logo_url: Optional[str]
    stt_reset_rule: str
    current_stt_counter: int
    auto_print_on_confirm: bool
    confirm_before_print: bool
    print_paper_size: str
    inventory_enabled: bool
    message_template: str
    created_at: datetime


class ShopMemberCreateRequest(BaseModel):
    email: EmailStr
    full_name: str = Field("Nhân viên", min_length=2, max_length=255)
    password: Optional[str] = Field(None, min_length=6, max_length=128)
    role: str = Field("STAFF", pattern="^(OWNER|ADMIN|STAFF)$")


class ShopMemberResponse(BaseModel):
    id: str
    shop_id: str
    user_id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime


# ==============================================================================
# CONNECTED ACCOUNTS & LIVE SESSIONS
# ==============================================================================

class ConnectedAccountCreateRequest(BaseModel):
    platform: str = Field(..., pattern="^(FACEBOOK_PAGE|FACEBOOK_PERSONAL|DEMO)$")
    external_id: str = Field(..., min_length=1, max_length=128)
    name: str = Field(..., min_length=1, max_length=255)
    access_token: Optional[str] = None
    granted_permissions: Optional[List[str]] = None


class ConnectedAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    shop_id: str
    platform: str
    external_id: str
    name: str
    connection_status: str
    granted_permissions: Optional[str]
    missing_permissions: Optional[str]
    last_error: Optional[str]
    created_at: datetime
    updated_at: datetime


class LiveSessionCreateRequest(BaseModel):
    connected_account_id: Optional[str] = None
    external_video_id: Optional[str] = Field(None, max_length=128)
    title: str = Field(..., min_length=2, max_length=255)
    source_type: str = Field(..., pattern="^(FACEBOOK_PAGE|FACEBOOK_PERSONAL|DEMO)$")


class LiveSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    shop_id: str
    connected_account_id: Optional[str]
    external_video_id: Optional[str]
    title: str
    source_type: str
    connection_mode: str
    status: str
    session_stt_counter: int
    started_at: datetime
    ended_at: Optional[datetime]


# ==============================================================================
# PRODUCTS & VARIANTS
# ==============================================================================

class ProductVariantCreate(BaseModel):
    sku: Optional[str] = None
    color: Optional[str] = None
    size: Optional[str] = None
    price_override: Optional[float] = Field(None, ge=0)
    stock_quantity: int = Field(0, ge=0)
    is_active: bool = True


class ProductVariantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    product_id: str
    sku: Optional[str]
    color: Optional[str]
    size: Optional[str]
    price_override: Optional[float]
    stock_quantity: int
    is_active: bool


class ProductCreateRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    unit_price: float = Field(..., ge=0)
    is_active: bool = True
    track_inventory: bool = False
    stock_quantity: int = Field(0, ge=0)
    variants: Optional[List[ProductVariantCreate]] = None

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        cleaned = v.strip().upper()
        if not cleaned:
            raise ValueError("Mã sản phẩm không được để trống")
        return cleaned


class ProductUpdateRequest(BaseModel):
    code: Optional[str] = Field(None, min_length=1, max_length=64)
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    unit_price: Optional[float] = Field(None, ge=0)
    is_active: Optional[bool] = None
    track_inventory: Optional[bool] = None
    stock_quantity: Optional[int] = Field(None, ge=0)


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    shop_id: str
    code: str
    name: str
    description: Optional[str]
    unit_price: float
    is_active: bool
    track_inventory: bool
    stock_quantity: int
    variants: List[ProductVariantResponse] = []
    created_at: datetime
    updated_at: datetime


# ==============================================================================
# COMMENTS & PARSER
# ==============================================================================

class CommentManualCreateRequest(BaseModel):
    live_session_id: str
    commenter_name: str = Field(..., min_length=1, max_length=255)
    commenter_external_id: Optional[str] = None
    commenter_avatar: Optional[str] = None
    raw_message: str = Field(..., min_length=1, max_length=2000)
    external_comment_id: Optional[str] = None
    commented_at: Optional[datetime] = None


class CommentBatchManualCreateRequest(BaseModel):
    live_session_id: str
    lines: List[CommentManualCreateRequest] = Field(..., min_length=1, max_length=200)


class CommentParsePreviewRequest(BaseModel):
    raw_message: str = Field(..., min_length=1, max_length=2000)


class CommentParseResult(BaseModel):
    product_code: Optional[str]
    matched_product_id: Optional[str] = None
    matched_product_name: Optional[str] = None
    matched_unit_price: Optional[float] = None
    quantity: int
    color: Optional[str]
    size: Optional[str]
    has_buy_intent: bool
    confidence: float
    missing_fields: List[str]
    is_ambiguous: bool
    candidate_codes: List[str] = []


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    shop_id: str
    live_session_id: str
    customer_id: Optional[str]
    source_type: str
    connection_mode: str
    external_page_id: Optional[str]
    external_live_id: Optional[str]
    external_comment_id: str
    commenter_external_id: Optional[str]
    commenter_name: str
    commenter_avatar: Optional[str]
    raw_message: str
    parsed_product_code: Optional[str]
    parsed_quantity: int
    parsed_color: Optional[str]
    parsed_size: Optional[str]
    parsed_intent: bool
    parse_confidence: float
    missing_fields: Optional[str]
    is_ambiguous: bool
    status: str
    error_message: Optional[str]
    commented_at: datetime
    received_at: datetime


# ==============================================================================
# ORDERS ("ĐÃ CHỐT" WORKFLOW)
# ==============================================================================

class ConfirmOrderFromCommentRequest(BaseModel):
    comment_id: str
    idempotency_key: str = Field(..., min_length=4, max_length=128)
    product_code: Optional[str] = None
    product_id: Optional[str] = None
    variant_id: Optional[str] = None
    color: Optional[str] = None
    size: Optional[str] = None
    quantity: Optional[int] = Field(None, ge=1, le=10000)
    notes: Optional[str] = Field(None, max_length=1000)
    force_confirm_ambiguous: bool = False
    trigger_messenger: bool = True
    trigger_print: bool = True
    print_mode: str = Field("BROWSER", pattern="^(BROWSER|PRINT_BRIDGE)$")


class OrderStatusUpdateRequest(BaseModel):
    status: str = Field(..., pattern="^(CONFIRMED|PENDING_CONFIRMATION|CANCELLED)$")
    notes: Optional[str] = None


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    product_id: str
    variant_id: Optional[str]
    product_code_snapshot: str
    product_name_snapshot: str
    variant_snapshot: Optional[str]
    quantity: int
    unit_price_snapshot: float
    line_total: float


class MessageLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    shop_id: str
    order_id: str
    comment_id: Optional[str]
    provider_mode: str
    external_message_id: Optional[str]
    rendered_content: str
    status: str
    retry_count: int
    max_retries: int
    error_code: Optional[str]
    error_reason: Optional[str]
    messenger_thread_url: Optional[str]
    sent_at: Optional[datetime]
    created_at: datetime


class PrintJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    shop_id: str
    order_id: str
    print_mode: str
    paper_size: str
    status: str
    snapshot_payload: str
    rendered_html: str
    error_message: Optional[str]
    printed_at: Optional[datetime]
    created_at: datetime


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    shop_id: str
    live_session_id: Optional[str]
    comment_id: Optional[str]
    customer_id: str
    confirmed_by_user_id: str
    order_code: str
    customer_stt: int
    status: str
    subtotal: float
    notes: Optional[str]
    idempotency_key: str
    confirmed_at: datetime
    created_at: datetime
    items: List[OrderItemResponse] = []
    message_logs: List[MessageLogResponse] = []
    print_jobs: List[PrintJobResponse] = []


class ConfirmOrderWorkflowResponse(BaseModel):
    order: OrderResponse
    comment_status: str
    message_log: Optional[MessageLogResponse] = None
    print_job: Optional[PrintJobResponse] = None
    was_idempotent_replay: bool = False


# ==============================================================================
# PRINT & NOTIFICATION SETTINGS
# ==============================================================================

class NotificationSettingUpdateRequest(BaseModel):
    font_family: Optional[str] = None
    font_size_px: Optional[int] = Field(None, ge=9, le=28)
    margin_mm: Optional[int] = Field(None, ge=0, le=30)
    header_note: Optional[str] = None
    footer_note: Optional[str] = None
    enable_auto_messenger: Optional[bool] = None
    messenger_template: Optional[str] = None


class NotificationSettingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    shop_id: str
    font_family: str
    font_size_px: int
    margin_mm: int
    header_note: Optional[str]
    footer_note: Optional[str]
    enable_auto_messenger: bool
    messenger_template: str
    updated_at: datetime


# ==============================================================================
# DASHBOARD METRICS
# ==============================================================================

class DashboardMetricsResponse(BaseModel):
    total_comments: int
    confirmed_comments: int
    unique_confirmed_customers: int
    total_orders: int
    pending_orders: int
    cancelled_orders: int
    messages_sent: int
    messages_failed: int
    messages_pending_or_manual: int
    prints_printed: int
    prints_failed: int
    prints_queued: int
    confirmed_revenue: float
    metric_definitions: Dict[str, str]
