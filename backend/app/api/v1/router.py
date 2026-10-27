from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy import asc, desc, func, or_, text
from sqlalchemy.orm import Session

from app.api.deps import enforce_rate_limit, get_current_user, get_shop_access
from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    encrypt_secret,
    hash_password,
    verify_meta_webhook_signature,
    verify_password,
)
from app.models import (
    AuditLog,
    Comment,
    CommentStatus,
    ConnectedAccount,
    ConnectionStatus,
    Customer,
    LiveSession,
    LiveSessionStatus,
    MessageLog,
    MessageStatus,
    NotificationSetting,
    Order,
    OrderItem,
    OrderStatus,
    PrintJob,
    PrintJobStatus,
    Product,
    ProductVariant,
    Shop,
    ShopMember,
    ShopRole,
    SourcePlatform,
    User,
    WebhookEvent,
)
from app.schemas import (
    CommentBatchManualCreateRequest,
    CommentManualCreateRequest,
    CommentParsePreviewRequest,
    CommentParseResult,
    CommentResponse,
    ConfirmOrderFromCommentRequest,
    ConfirmOrderWorkflowResponse,
    ConnectedAccountCreateRequest,
    ConnectedAccountResponse,
    DashboardMetricsResponse,
    LiveSessionCreateRequest,
    LiveSessionResponse,
    MessageLogResponse,
    NotificationSettingResponse,
    NotificationSettingUpdateRequest,
    OrderResponse,
    OrderStatusUpdateRequest,
    PrintJobResponse,
    ProductCreateRequest,
    ProductResponse,
    ProductUpdateRequest,
    ShopCreateRequest,
    ShopMemberCreateRequest,
    ShopMemberResponse,
    ShopResponse,
    ShopUpdateRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.services.comment_parser import parse_livestream_comment
from app.services.meta_service import (
    REQUIRED_PAGE_PERMISSIONS,
    dispatch_order_confirmation_message,
)
from app.services.order_service import confirm_order_from_comment
from app.services.print_service import create_and_dispatch_print_job

api_router = APIRouter(dependencies=[Depends(enforce_rate_limit)])


# ==============================================================================
# 1. AUTHENTICATION (/auth)
# ==============================================================================

@api_router.post("/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register_user(req: UserRegisterRequest, db: Session = Depends(get_db)):
    email_clean = req.email.strip().lower()
    existing = db.query(User).filter(User.email == email_clean).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email này đã được đăng ký.",
        )
    user = User(
        email=email_clean,
        full_name=req.full_name.strip(),
        hashed_password=hash_password(req.password),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(subject=user.id)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@api_router.post("/auth/login", response_model=TokenResponse)
def login_user(req: UserLoginRequest, db: Session = Depends(get_db)):
    email_clean = req.email.strip().lower()
    user = db.query(User).filter(User.email == email_clean).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không chính xác.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản đã bị vô hiệu hóa.",
        )
    token = create_access_token(subject=user.id)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@api_router.get("/auth/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)


# ==============================================================================
# 2. SHOPS & SETTINGS (/shops)
# ==============================================================================

def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.lower()).strip("-")
    return f"{slug or 'shop'}-{uuid.uuid4().hex[:6]}"


@api_router.post("/shops", response_model=ShopResponse, status_code=status.HTTP_201_CREATED)
def create_shop(
    req: ShopCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    shop = Shop(
        name=req.name.strip(),
        slug=_slugify(req.name),
        phone=req.phone,
        address=req.address,
        logo_url=req.logo_url,
        stt_reset_rule=req.stt_reset_rule,
        print_paper_size=req.print_paper_size,
        auto_print_on_confirm=req.auto_print_on_confirm,
        confirm_before_print=req.confirm_before_print,
        inventory_enabled=req.inventory_enabled,
    )
    db.add(shop)
    db.flush()

    member = ShopMember(
        shop_id=shop.id,
        user_id=current_user.id,
        role=ShopRole.OWNER.value,
        is_active=True,
    )
    db.add(member)

    notif = NotificationSetting(shop_id=shop.id)
    db.add(notif)

    audit = AuditLog(
        shop_id=shop.id,
        user_id=current_user.id,
        action="SHOP_CREATED",
        entity_type="Shop",
        entity_id=shop.id,
        details=json.dumps({"name": shop.name}, ensure_ascii=False),
    )
    db.add(audit)
    db.commit()
    db.refresh(shop)
    return ShopResponse.model_validate(shop)


@api_router.get("/shops", response_model=List[ShopResponse])
def list_my_shops(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    memberships = (
        db.query(ShopMember)
        .filter(ShopMember.user_id == current_user.id, ShopMember.is_active == True)  # noqa: E712
        .all()
    )
    shop_ids = [m.shop_id for m in memberships]
    if not shop_ids:
        return []
    shops = db.query(Shop).filter(Shop.id.in_(shop_ids)).order_by(Shop.created_at.asc()).all()
    return [ShopResponse.model_validate(s) for s in shops]


@api_router.get("/shops/{shop_id}", response_model=ShopResponse)
def get_shop_detail(
    shop_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    shop, _ = get_shop_access(shop_id, current_user, db)
    return ShopResponse.model_validate(shop)


@api_router.patch("/shops/{shop_id}", response_model=ShopResponse)
def update_shop(
    shop_id: str,
    req: ShopUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    shop, _ = get_shop_access(
        shop_id, current_user, db, required_roles=[ShopRole.OWNER.value, ShopRole.ADMIN.value]
    )
    for field, val in req.model_dump(exclude_unset=True).items():
        setattr(shop, field, val)
    if req.message_template and shop.notification_setting:
        shop.notification_setting.messenger_template = req.message_template

    db.add(
        AuditLog(
            shop_id=shop.id,
            user_id=current_user.id,
            action="SHOP_UPDATED",
            entity_type="Shop",
            entity_id=shop.id,
            details=json.dumps(req.model_dump(exclude_unset=True), ensure_ascii=False),
        )
    )
    db.commit()
    db.refresh(shop)
    return ShopResponse.model_validate(shop)


@api_router.get("/shops/{shop_id}/print-settings", response_model=NotificationSettingResponse)
def get_print_settings(
    shop_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    shop, _ = get_shop_access(shop_id, current_user, db)
    if not shop.notification_setting:
        ns = NotificationSetting(shop_id=shop.id)
        db.add(ns)
        db.commit()
        db.refresh(ns)
        return NotificationSettingResponse.model_validate(ns)
    return NotificationSettingResponse.model_validate(shop.notification_setting)


@api_router.put("/shops/{shop_id}/print-settings", response_model=NotificationSettingResponse)
def update_print_settings(
    shop_id: str,
    req: NotificationSettingUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    shop, _ = get_shop_access(
        shop_id, current_user, db, required_roles=[ShopRole.OWNER.value, ShopRole.ADMIN.value]
    )
    ns = shop.notification_setting
    if not ns:
        ns = NotificationSetting(shop_id=shop.id)
        db.add(ns)
        db.flush()

    for field, val in req.model_dump(exclude_unset=True).items():
        setattr(ns, field, val)
    if req.messenger_template:
        shop.message_template = req.messenger_template
    db.commit()
    db.refresh(ns)
    return NotificationSettingResponse.model_validate(ns)


# ==============================================================================
# 3. MEMBERS & ROLES (/shops/{shop_id}/members)
# ==============================================================================

@api_router.get("/shops/{shop_id}/members", response_model=List[ShopMemberResponse])
def list_shop_members(
    shop_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_shop_access(shop_id, current_user, db)
    members = db.query(ShopMember).filter(ShopMember.shop_id == shop_id).all()
    results: List[ShopMemberResponse] = []
    for m in members:
        u = db.query(User).filter(User.id == m.user_id).first()
        if u:
            results.append(
                ShopMemberResponse(
                    id=m.id,
                    shop_id=m.shop_id,
                    user_id=m.user_id,
                    email=u.email,
                    full_name=u.full_name,
                    role=m.role,
                    is_active=m.is_active,
                    created_at=m.created_at,
                )
            )
    return results


@api_router.post(
    "/shops/{shop_id}/members",
    response_model=ShopMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_shop_member(
    shop_id: str,
    req: ShopMemberCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    shop, _ = get_shop_access(
        shop_id, current_user, db, required_roles=[ShopRole.OWNER.value, ShopRole.ADMIN.value]
    )
    email_clean = req.email.strip().lower()
    target_user = db.query(User).filter(User.email == email_clean).first()
    if not target_user:
        pwd = req.password or "Staff@123456"
        target_user = User(
            email=email_clean,
            full_name=req.full_name.strip(),
            hashed_password=hash_password(pwd),
            is_active=True,
        )
        db.add(target_user)
        db.flush()

    existing = (
        db.query(ShopMember)
        .filter(ShopMember.shop_id == shop.id, ShopMember.user_id == target_user.id)
        .first()
    )
    if existing:
        existing.role = req.role
        existing.is_active = True
        member = existing
    else:
        member = ShopMember(
            shop_id=shop.id,
            user_id=target_user.id,
            role=req.role,
            is_active=True,
        )
        db.add(member)

    db.add(
        AuditLog(
            shop_id=shop.id,
            user_id=current_user.id,
            action="MEMBER_ADDED_OR_UPDATED",
            entity_type="ShopMember",
            entity_id=target_user.id,
            details=json.dumps({"email": target_user.email, "role": req.role}, ensure_ascii=False),
        )
    )
    db.commit()
    db.refresh(member)
    return ShopMemberResponse(
        id=member.id,
        shop_id=member.shop_id,
        user_id=member.user_id,
        email=target_user.email,
        full_name=target_user.full_name,
        role=member.role,
        is_active=member.is_active,
        created_at=member.created_at,
    )


# ==============================================================================
# 4. META OAUTH & CONNECTED ACCOUNTS (/meta, /shops/{shop_id}/connected-accounts)
# ==============================================================================

@api_router.get("/meta/integration-status")
def get_meta_integration_status(current_user: User = Depends(get_current_user)):
    """
    Transparently reports whether real Meta credentials are configured or whether
    the system is in Mock/Blocked mode. Never fakes a real Facebook connection.
    """
    has_creds = settings.has_real_meta_credentials
    return {
        "api_version": settings.META_API_VERSION,
        "has_real_meta_credentials": has_creds,
        "allow_mock_in_current_env": settings.allow_mock_provider,
        "real_messenger_status": "READY_FOR_OAUTH" if has_creds else "BLOCKED_MISSING_CREDENTIALS",
        "personal_profile_policy": (
            "Meta Graph API chính thức không cho phép tự động đọc bình luận hoặc gửi Private Reply "
            "trên trang cá nhân tiêu chuẩn. Hệ thống sử dụng chế độ MANUAL_MODE hợp pháp."
        ),
        "required_permissions": sorted(list(REQUIRED_PAGE_PERMISSIONS)),
        "oauth_authorization_url": (
            f"https://www.facebook.com/{settings.META_API_VERSION}/dialog/oauth"
            f"?client_id={settings.META_APP_ID}&redirect_uri={settings.META_REDIRECT_URI}"
            f"&scope={','.join(sorted(list(REQUIRED_PAGE_PERMISSIONS)))}"
            if has_creds
            else None
        ),
    }


@api_router.get("/shops/{shop_id}/meta/oauth-url")
def get_shop_meta_oauth_url(
    shop_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generates the 1-Click Facebook Login OAuth URL for a specific shop so the customer
    (livestream seller) only needs to click 1 button to connect all their Fanpages.
    """
    shop, _ = get_shop_access(
        shop_id, current_user, db, required_roles=[ShopRole.OWNER.value, ShopRole.ADMIN.value]
    )
    if not settings.has_real_meta_credentials:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Chủ hệ thống (Admin) chưa cấu hình META_APP_ID và META_APP_SECRET trong file .env. "
                "Bạn chỉ cần tạo 1 Meta App duy nhất cho toàn bộ phần mềm, sau đó mọi khách hàng "
                "mua app chỉ cần bấm nút này 1 lần là tự động kết nối Fanpage!"
            ),
        )
    extra_scopes = {s.strip() for s in settings.META_OAUTH_EXTRA_SCOPES.split(",") if s.strip()}
    scopes = ",".join(sorted(list(REQUIRED_PAGE_PERMISSIONS | {"pages_manage_metadata"} | extra_scopes)))
    url = (
        f"https://www.facebook.com/{settings.META_API_VERSION}/dialog/oauth"
        f"?client_id={settings.META_APP_ID}"
        f"&redirect_uri={settings.META_REDIRECT_URI}"
        f"&state={shop.id}"
        f"&scope={scopes}"
        f"&auth_type=rerequest"
    )
    return {"oauth_url": url}


@api_router.get("/meta/oauth/callback")
def handle_meta_oauth_callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    1-Click OAuth Callback for customers:
    Exchanges `code` for User Access Token -> fetches `/me/accounts` (all Fanpages of the seller)
    -> automatically saves Page IDs & encrypted Page Access Tokens -> redirects back to Frontend!
    """
    import httpx
    from fastapi.responses import RedirectResponse

    if error or not code or not state:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}?meta_oauth=cancelled")

    shop = db.query(Shop).filter(Shop.id == state).first()
    if not shop or not settings.has_real_meta_credentials:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}?meta_oauth=error")

    token_url = f"https://graph.facebook.com/{settings.META_API_VERSION}/oauth/access_token"
    try:
        with httpx.Client(timeout=15.0) as client:
            tok_resp = client.get(
                token_url,
                params={
                    "client_id": settings.META_APP_ID,
                    "client_secret": settings.META_APP_SECRET,
                    "redirect_uri": settings.META_REDIRECT_URI,
                    "code": code,
                },
            )
            if tok_resp.status_code != 200:
                return RedirectResponse(url=f"{settings.FRONTEND_URL}?meta_oauth=token_exchange_failed")
            user_access_token = tok_resp.json().get("access_token")

            # Fetch all Fanpages managed by this customer
            pages_resp = client.get(
                f"https://graph.facebook.com/{settings.META_API_VERSION}/me/accounts",
                params={"fields": "id,name,access_token,tasks", "limit": 100, "access_token": user_access_token},
            )
            if pages_resp.status_code != 200:
                return RedirectResponse(url=f"{settings.FRONTEND_URL}?meta_oauth=fetch_pages_failed")

            pages_data = list(pages_resp.json().get("data", []))
            known_pids = {str(p.get("id", "")) for p in pages_data if p.get("id")}

            # Also inspect /debug_token granular_scopes (catches New Pages Experience / Business Portfolio Pages
            # that do not appear in /me/accounts without business_management scope)
            granted_scopes: set[str] = set()
            granular_target_ids: list[str] = []
            try:
                app_token = f"{settings.META_APP_ID}|{settings.META_APP_SECRET}"
                dbg_resp = client.get(
                    f"https://graph.facebook.com/{settings.META_API_VERSION}/debug_token",
                    params={"input_token": user_access_token, "access_token": app_token},
                )
                if dbg_resp.status_code == 200:
                    dbg_data = dbg_resp.json().get("data", {})
                    granted_scopes = set(dbg_data.get("scopes") or [])
                    for gs in dbg_data.get("granular_scopes") or []:
                        for tid in gs.get("target_ids") or []:
                            tid_str = str(tid).strip()
                            if tid_str and tid_str not in granular_target_ids:
                                granular_target_ids.append(tid_str)
            except Exception:
                pass

            for tid in granular_target_ids:
                if tid in known_pids:
                    continue
                try:
                    p_resp = client.get(
                        f"https://graph.facebook.com/{settings.META_API_VERSION}/{tid}",
                        params={"fields": "id,name,access_token", "access_token": user_access_token},
                    )
                    if p_resp.status_code != 200:
                        p_resp = client.get(
                            f"https://graph.facebook.com/{settings.META_API_VERSION}/{tid}",
                            params={"fields": "id,name", "access_token": user_access_token},
                        )
                    if p_resp.status_code == 200:
                        p_info = p_resp.json()
                        if p_info.get("id"):
                            pages_data.append(
                                {
                                    "id": str(p_info["id"]),
                                    "name": p_info.get("name") or f"Fanpage {p_info['id']}",
                                    "access_token": p_info.get("access_token") or user_access_token,
                                }
                            )
                            known_pids.add(str(p_info["id"]))
                except Exception:
                    pass

            if not pages_data:
                if not granted_scopes:
                    try:
                        perm_resp = client.get(
                            f"https://graph.facebook.com/{settings.META_API_VERSION}/me/permissions",
                            params={"access_token": user_access_token},
                        )
                        if perm_resp.status_code == 200:
                            granted_scopes = {
                                item.get("permission")
                                for item in perm_resp.json().get("data", [])
                                if item.get("status") == "granted" and item.get("permission")
                            }
                    except Exception:
                        pass

                empty_reason = (
                    "app_role_not_accepted"
                    if "pages_show_list" not in granted_scopes
                    else "no_page_selected"
                )
                # Revoke the 0-page OAuth grant on Facebook so the next click forces the Page selection popup again
                try:
                    client.delete(
                        f"https://graph.facebook.com/{settings.META_API_VERSION}/me/permissions",
                        params={"access_token": user_access_token},
                    )
                except Exception:
                    pass
                return RedirectResponse(
                    url=f"{settings.FRONTEND_URL}?meta_oauth=success&pages_count=0&reason={empty_reason}"
                )
            for p in pages_data:
                pid = str(p.get("id", ""))
                pname = p.get("name") or f"Fanpage {pid}"
                ptoken = p.get("access_token")
                if not pid or not ptoken:
                    continue

                existing = (
                    db.query(ConnectedAccount)
                    .filter(
                        ConnectedAccount.shop_id == shop.id,
                        ConnectedAccount.platform == SourcePlatform.FACEBOOK_PAGE.value,
                        ConnectedAccount.external_id == pid,
                    )
                    .first()
                )
                encrypted_tok = encrypt_secret(ptoken)
                perms_str = ",".join(sorted(list(REQUIRED_PAGE_PERMISSIONS)))
                if existing:
                    existing.name = pname
                    existing.encrypted_access_token = encrypted_tok
                    existing.connection_status = ConnectionStatus.CONNECTED.value
                    existing.granted_permissions = perms_str
                    existing.missing_permissions = None
                    existing.last_error = None
                    acc_obj = existing
                else:
                    acc_obj = ConnectedAccount(
                        shop_id=shop.id,
                        platform=SourcePlatform.FACEBOOK_PAGE.value,
                        external_id=pid,
                        name=pname,
                        encrypted_access_token=encrypted_tok,
                        connection_status=ConnectionStatus.CONNECTED.value,
                        granted_permissions=perms_str,
                    )
                    db.add(acc_obj)
                db.flush()

                existing_session = (
                    db.query(LiveSession)
                    .filter(
                        LiveSession.shop_id == shop.id,
                        LiveSession.connected_account_id == acc_obj.id,
                    )
                    .first()
                )
                if not existing_session:
                    db.add(
                        LiveSession(
                            shop_id=shop.id,
                            connected_account_id=acc_obj.id,
                            external_video_id=f"live_{uuid.uuid4().hex[:8]}",
                            title=f"Live {pname}",
                            source_type=SourcePlatform.FACEBOOK_PAGE.value,
                            connection_mode=ConnectionStatus.CONNECTED.value,
                            status="ACTIVE",
                        )
                    )

                # Automatically subscribe the Fanpage to our Meta Webhook (`feed` field)
                try:
                    client.post(
                        f"https://graph.facebook.com/{settings.META_API_VERSION}/{pid}/subscribed_apps",
                        params={"subscribed_fields": "feed", "access_token": ptoken},
                    )
                except Exception:
                    pass
            db.commit()
            return RedirectResponse(
                url=f"{settings.FRONTEND_URL}?meta_oauth=success&pages_count={len(pages_data)}"
            )
    except Exception:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}?meta_oauth=network_error")

    return RedirectResponse(url=f"{settings.FRONTEND_URL}?meta_oauth=success")


@api_router.get("/shops/{shop_id}/connected-accounts", response_model=List[ConnectedAccountResponse])
def list_connected_accounts(
    shop_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_shop_access(shop_id, current_user, db)
    accounts = (
        db.query(ConnectedAccount)
        .filter(ConnectedAccount.shop_id == shop_id)
        .order_by(ConnectedAccount.created_at.desc())
        .all()
    )
    return [ConnectedAccountResponse.model_validate(a) for a in accounts]


@api_router.post(
    "/shops/{shop_id}/connected-accounts",
    response_model=ConnectedAccountResponse,
    status_code=status.HTTP_201_CREATED,
)
def connect_account(
    shop_id: str,
    req: ConnectedAccountCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    shop, _ = get_shop_access(
        shop_id, current_user, db, required_roles=[ShopRole.OWNER.value, ShopRole.ADMIN.value]
    )

    resolved_ext_id = req.external_id.strip()
    resolved_name = req.name.strip()
    resolved_token = req.access_token.strip() if req.access_token else None

    # Auto-discover Fanpage ID, Name, and Page Access Token when a real Meta token (EAA...) is provided
    if (
        req.platform == SourcePlatform.FACEBOOK_PAGE.value
        and resolved_token
        and resolved_token.startswith("EAA")
    ):
        import httpx

        try:
            with httpx.Client(timeout=10.0) as client:
                # 1. Check if the pasted token is a User Access Token that manages Fanpages
                pages_resp = client.get(
                    f"https://graph.facebook.com/{settings.META_API_VERSION}/me/accounts",
                    params={"fields": "id,name,access_token", "limit": 100, "access_token": resolved_token},
                )
                pages_list = (
                    pages_resp.json().get("data", []) if pages_resp.status_code == 200 else []
                )
                if pages_list:
                    matched_page = next(
                        (p for p in pages_list if str(p.get("id")) == resolved_ext_id),
                        pages_list[0],
                    )
                    if matched_page.get("id"):
                        resolved_ext_id = str(matched_page["id"])
                    if matched_page.get("name"):
                        resolved_name = str(matched_page["name"])
                    if matched_page.get("access_token"):
                        resolved_token = str(matched_page["access_token"])
                else:
                    # 2. Check if the pasted token is already a Page Access Token (or User Token with known Page ID)
                    target_node = (
                        resolved_ext_id
                        if resolved_ext_id and resolved_ext_id != "auto"
                        else "me"
                    )
                    me_resp = client.get(
                        f"https://graph.facebook.com/{settings.META_API_VERSION}/{target_node}",
                        params={"fields": "id,name,access_token", "access_token": resolved_token},
                    )
                    if me_resp.status_code != 200:
                        me_resp = client.get(
                            f"https://graph.facebook.com/{settings.META_API_VERSION}/{target_node}",
                            params={"fields": "id,name", "access_token": resolved_token},
                        )
                    if me_resp.status_code == 200:
                        me_data = me_resp.json()
                        if me_data.get("id"):
                            resolved_ext_id = str(me_data["id"])
                        if me_data.get("name"):
                            resolved_name = str(me_data["name"])
                        if me_data.get("access_token"):
                            resolved_token = str(me_data["access_token"])
        except Exception:
            pass

    granted = set(req.granted_permissions or [])
    missing = sorted(list(REQUIRED_PAGE_PERMISSIONS - granted)) if req.platform == SourcePlatform.FACEBOOK_PAGE.value else []

    if req.platform == SourcePlatform.FACEBOOK_PERSONAL.value:
        conn_status = ConnectionStatus.MANUAL_MODE.value
        last_error = "Trang cá nhân sử dụng chế độ nhập thủ công (MANUAL_MODE) theo chính sách Meta."
    elif req.platform == SourcePlatform.DEMO.value:
        if not settings.allow_mock_provider:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Không được phép bật nguồn DEMO trong môi trường Production.",
            )
        conn_status = ConnectionStatus.DEMO.value
        last_error = None
    else:
        # FACEBOOK_PAGE
        if resolved_token and not req.granted_permissions:
            granted = set(REQUIRED_PAGE_PERMISSIONS)
            missing = []
        if not settings.has_real_meta_credentials and not resolved_token:
            conn_status = ConnectionStatus.MISSING_CREDENTIALS.value
            last_error = "Chưa cấu hình META_APP_ID / META_APP_SECRET hoặc chưa cấp Page Access Token."
        elif missing:
            conn_status = ConnectionStatus.NEEDS_PERMISSION.value
            last_error = f"Thiếu quyền Meta bắt buộc: {', '.join(missing)}"
        else:
            conn_status = ConnectionStatus.CONNECTED.value
            last_error = None

    encrypted_token = encrypt_secret(resolved_token) if resolved_token else None

    existing = (
        db.query(ConnectedAccount)
        .filter(
            ConnectedAccount.shop_id == shop.id,
            ConnectedAccount.platform == req.platform,
            ConnectedAccount.external_id == resolved_ext_id,
        )
        .first()
    )
    if existing:
        existing.name = resolved_name
        existing.connection_status = conn_status
        existing.encrypted_access_token = encrypted_token
        existing.granted_permissions = ",".join(sorted(list(granted))) if granted else None
        existing.missing_permissions = ",".join(missing) if missing else None
        existing.last_error = last_error
        acc = existing
    else:
        acc = ConnectedAccount(
            shop_id=shop.id,
            platform=req.platform,
            external_id=resolved_ext_id,
            name=resolved_name,
            connection_status=conn_status,
            encrypted_access_token=encrypted_token,
            granted_permissions=",".join(sorted(list(granted))) if granted else None,
            missing_permissions=",".join(missing) if missing else None,
            last_error=last_error,
        )
        db.add(acc)

    db.commit()
    db.refresh(acc)
    return ConnectedAccountResponse.model_validate(acc)


# ==============================================================================
# 5. LIVE SESSIONS (/shops/{shop_id}/live-sessions)
# ==============================================================================

@api_router.get("/shops/{shop_id}/live-sessions", response_model=List[LiveSessionResponse])
def list_live_sessions(
    shop_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_shop_access(shop_id, current_user, db)
    sessions = (
        db.query(LiveSession)
        .filter(LiveSession.shop_id == shop_id)
        .order_by(LiveSession.started_at.desc())
        .all()
    )
    if not sessions:
        first_acc = (
            db.query(ConnectedAccount)
            .filter(ConnectedAccount.shop_id == shop_id)
            .order_by(ConnectedAccount.updated_at.desc())
            .first()
        )
        if first_acc:
            auto_sess = LiveSession(
                shop_id=shop_id,
                connected_account_id=first_acc.id,
                external_video_id=f"live_{uuid.uuid4().hex[:8]}",
                title=f"Live {first_acc.name}",
                source_type=first_acc.platform,
                connection_mode=first_acc.connection_status,
                status=LiveSessionStatus.LIVE.value,
            )
            db.add(auto_sess)
            db.commit()
            db.refresh(auto_sess)
            sessions = [auto_sess]
    return [LiveSessionResponse.model_validate(s) for s in sessions]


@api_router.post(
    "/shops/{shop_id}/live-sessions",
    response_model=LiveSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_live_session(
    shop_id: str,
    req: LiveSessionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    shop, _ = get_shop_access(shop_id, current_user, db)
    conn_mode = ConnectionStatus.MANUAL_MODE.value

    if req.source_type == SourcePlatform.DEMO.value:
        if not settings.allow_mock_provider:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Không cho phép tạo phiên DEMO trong môi trường Production.",
            )
        conn_mode = ConnectionStatus.DEMO.value
    elif req.connected_account_id:
        acc = (
            db.query(ConnectedAccount)
            .filter(
                ConnectedAccount.id == req.connected_account_id,
                ConnectedAccount.shop_id == shop.id,
            )
            .first()
        )
        if acc:
            conn_mode = acc.connection_status

    session_obj = LiveSession(
        shop_id=shop.id,
        connected_account_id=req.connected_account_id,
        external_video_id=req.external_video_id or f"live_{uuid.uuid4().hex[:8]}",
        title=req.title.strip(),
        source_type=req.source_type,
        connection_mode=conn_mode,
        status=LiveSessionStatus.LIVE.value,
    )
    db.add(session_obj)
    db.commit()
    db.refresh(session_obj)
    return LiveSessionResponse.model_validate(session_obj)


@api_router.post("/shops/{shop_id}/live-sessions/{session_id}/end", response_model=LiveSessionResponse)
def end_live_session(
    shop_id: str,
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_shop_access(shop_id, current_user, db)
    session_obj = (
        db.query(LiveSession)
        .filter(LiveSession.id == session_id, LiveSession.shop_id == shop_id)
        .first()
    )
    if not session_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiên live.")
    session_obj.status = LiveSessionStatus.ENDED.value
    session_obj.ended_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session_obj)
    return LiveSessionResponse.model_validate(session_obj)


@api_router.post("/shops/{shop_id}/live-sessions/{session_id}/sync-facebook-comments")
def sync_facebook_comments_from_graph_api(
    shop_id: str,
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Directly polls Meta Graph API (`GET /{external_video_id}/comments`) using the connected
    Fanpage's encrypted Page Access Token so the shop owner can test a real Facebook Page
    live video / post immediately without needing manual session setup.
    """
    import httpx
    from app.core.security import decrypt_secret

    shop, _ = get_shop_access(shop_id, current_user, db)

    conn_acc = (
        db.query(ConnectedAccount)
        .filter(
            ConnectedAccount.shop_id == shop.id,
            ConnectedAccount.platform == SourcePlatform.FACEBOOK_PAGE.value,
        )
        .order_by(ConnectedAccount.updated_at.desc())
        .first()
    )
    if not conn_acc or not conn_acc.encrypted_access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chưa có Fanpage nào được kết nối. Vui lòng bấm Kết Nối Nhanh Facebook ở mục Nguồn Kết Nối.",
        )

    live_session = (
        db.query(LiveSession)
        .filter(LiveSession.id == session_id, LiveSession.shop_id == shop.id)
        .first()
        if session_id != "auto"
        else None
    )
    if not live_session:
        live_session = (
            db.query(LiveSession)
            .filter(LiveSession.shop_id == shop.id)
            .order_by(LiveSession.started_at.desc())
            .first()
        )
    if not live_session:
        live_session = LiveSession(
            shop_id=shop.id,
            connected_account_id=conn_acc.id,
            external_video_id=f"live_{uuid.uuid4().hex[:8]}",
            title=f"Live {conn_acc.name}",
            source_type=SourcePlatform.FACEBOOK_PAGE.value,
            connection_mode=conn_acc.connection_status,
            status=LiveSessionStatus.LIVE.value,
        )
        db.add(live_session)
        db.flush()
    else:
        # Ensure session is linked to the real connected Fanpage if it was previously created as DEMO
        if live_session.source_type == SourcePlatform.DEMO.value or not live_session.connected_account_id:
            live_session.source_type = SourcePlatform.FACEBOOK_PAGE.value
            live_session.connected_account_id = conn_acc.id
            live_session.connection_mode = conn_acc.connection_status

    access_token = decrypt_secret(conn_acc.encrypted_access_token)
    headers = {"Authorization": f"Bearer {access_token}"}

    # Auto-discover active Live Videos AND latest Page posts so commenting on ANY recent post or live stream works seamlessly
    target_object_ids: List[str] = []
    if live_session.external_video_id and not live_session.external_video_id.startswith("live_"):
        target_object_ids.append(live_session.external_video_id)

    params_with_from = {
        "order": "reverse_chronological",
        "filter": "stream",
        "fields": "id,message,created_time,from",
        "limit": 50,
    }
    params_fallback = {
        "order": "reverse_chronological",
        "filter": "stream",
        "fields": "id,message,created_time",
        "limit": 50,
    }

    items: List[dict] = []
    last_err_msg: Optional[str] = None
    try:
        with httpx.Client(timeout=15.0) as client:
            # 1. Check active LIVE videos on the Page
            lv_resp = client.get(
                f"https://graph.facebook.com/{settings.META_API_VERSION}/{conn_acc.external_id}/live_videos",
                params={"broadcast_status": '["LIVE"]', "fields": "id,title", "limit": 2},
                headers=headers,
            )
            if lv_resp.status_code == 200 and lv_resp.json().get("data"):
                for lv in lv_resp.json()["data"]:
                    lv_id = str(lv.get("id", "")).strip()
                    if lv_id and lv_id not in target_object_ids:
                        target_object_ids.insert(0, lv_id)

            # 2. Check published_posts, posts, and feed on the Page (latest 5 posts)
            seen_comment_ids = set()
            for edge in ("published_posts", "posts", "feed"):
                feed_resp = client.get(
                    f"https://graph.facebook.com/{settings.META_API_VERSION}/{conn_acc.external_id}/{edge}",
                    params={"fields": "id,message,comments.limit(50){id,message,created_time,from}", "limit": 5},
                    headers=headers,
                )
                if feed_resp.status_code != 200:
                    # Retry without nested comments in case 'from' inside comments caused error
                    feed_resp = client.get(
                        f"https://graph.facebook.com/{settings.META_API_VERSION}/{conn_acc.external_id}/{edge}",
                        params={"fields": "id,message", "limit": 5},
                        headers=headers,
                    )
                if feed_resp.status_code == 200 and feed_resp.json().get("data"):
                    for post in feed_resp.json()["data"]:
                        post_id = str(post.get("id", "")).strip()
                        if post_id and post_id not in target_object_ids:
                            target_object_ids.append(post_id)
                        nested_cmts = (post.get("comments") or {}).get("data", [])
                        for c_item in nested_cmts:
                            c_id = str(c_item.get("id", "")).strip()
                            if c_id and c_id not in seen_comment_ids:
                                seen_comment_ids.add(c_id)
                                items.append(c_item)
                elif feed_resp.status_code != 200:
                    try:
                        err_data = feed_resp.json().get("error", {})
                        if err_data.get("message"):
                            last_err_msg = (
                                f"Token hiện tại thiếu quyền đọc bài viết/bình luận ({err_data.get('message')}). "
                                "Mã tạo ở mục Messenger chỉ có quyền nhắn tin (pages_messaging), cần thêm quyền "
                                "pages_read_engagement và pages_read_user_content!"
                            )
                    except Exception:
                        pass

            if target_object_ids and (
                not live_session.external_video_id or live_session.external_video_id.startswith("live_")
            ):
                live_session.external_video_id = target_object_ids[0]

            # 3. Fetch comments from discovered posts/live videos
            for obj_id in target_object_ids:
                url = f"https://graph.facebook.com/{settings.META_API_VERSION}/{obj_id}/comments"
                resp = client.get(url, params=params_with_from, headers=headers)
                if resp.status_code != 200:
                    resp = client.get(url, params=params_fallback, headers=headers)
                if resp.status_code == 200:
                    for c_item in resp.json().get("data", []):
                        c_id = str(c_item.get("id", "")).strip()
                        if c_id and c_id not in seen_comment_ids:
                            seen_comment_ids.add(c_id)
                            items.append(c_item)
                else:
                    try:
                        err_data = resp.json().get("error", {})
                        if err_data.get("message"):
                            last_err_msg = f"Lỗi từ Facebook ({err_data.get('code')}): {err_data.get('message')}"
                    except Exception:
                        last_err_msg = f"Meta Graph API trả về HTTP {resp.status_code}"
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Không thể kết nối tới Meta Graph API: {type(exc).__name__}",
        )

    if not items and last_err_msg:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=last_err_msg)
    ingested_count = 0
    for item in items:
        cid = str(item.get("id", "")).strip()
        msg = (item.get("message") or "").strip()
        if not cid or not msg:
            continue
        from_obj = item.get("from") or {}
        cname = from_obj.get("name") or "Khách Facebook"
        cuid = str(from_obj.get("id") or "") or None
        avatar = (
            from_obj.get("picture", {}).get("data", {}).get("url")
            if isinstance(from_obj.get("picture"), dict)
            else None
        )

        already = (
            db.query(Comment)
            .filter(Comment.shop_id == shop.id, Comment.external_comment_id == cid)
            .first()
        )
        if not already:
            ingested_count += 1

        _ingest_single_comment(
            db=db,
            shop=shop,
            live_session=live_session,
            commenter_name=cname,
            raw_message=msg,
            external_comment_id=cid,
            commenter_external_id=cuid,
            commenter_avatar=avatar,
            external_page_id=conn_acc.external_id,
        )

    db.commit()
    return {
        "status": "ok",
        "total_fetched_from_facebook": len(items),
        "new_comments_ingested": ingested_count,
    }


# ==============================================================================
# 6. PRODUCTS & CSV/XLSX IMPORT/EXPORT (/shops/{shop_id}/products)
# ==============================================================================

@api_router.get("/shops/{shop_id}/products", response_model=List[ProductResponse])
def list_products(
    shop_id: str,
    q: Optional[str] = Query(None),
    include_inactive: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_shop_access(shop_id, current_user, db)
    query = db.query(Product).filter(Product.shop_id == shop_id)
    if not include_inactive:
        query = query.filter(Product.is_active == True)  # noqa: E712
    if q and q.strip():
        kw = f"%{q.strip()}%"
        query = query.filter(or_(Product.code.ilike(kw), Product.name.ilike(kw)))
    products = query.order_by(Product.code.asc()).all()
    return [ProductResponse.model_validate(p) for p in products]


@api_router.post(
    "/shops/{shop_id}/products",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_product(
    shop_id: str,
    req: ProductCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    shop, _ = get_shop_access(shop_id, current_user, db)
    code_upper = req.code.strip().upper()
    existing = (
        db.query(Product)
        .filter(Product.shop_id == shop.id, Product.code == code_upper)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Mã sản phẩm '{code_upper}' đã tồn tại trong cửa hàng này.",
        )

    product = Product(
        shop_id=shop.id,
        code=code_upper,
        name=req.name.strip(),
        description=req.description,
        unit_price=req.unit_price,
        is_active=req.is_active,
        track_inventory=req.track_inventory,
        stock_quantity=req.stock_quantity,
    )
    db.add(product)
    db.flush()

    if req.variants:
        for v in req.variants:
            db.add(
                ProductVariant(
                    product_id=product.id,
                    shop_id=shop.id,
                    sku=v.sku,
                    color=v.color,
                    size=v.size,
                    price_override=v.price_override,
                    stock_quantity=v.stock_quantity,
                    is_active=v.is_active,
                )
            )

    db.commit()
    db.refresh(product)
    return ProductResponse.model_validate(product)


@api_router.patch("/shops/{shop_id}/products/{product_id}", response_model=ProductResponse)
def update_product(
    shop_id: str,
    product_id: str,
    req: ProductUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_shop_access(shop_id, current_user, db)
    product = (
        db.query(Product)
        .filter(Product.id == product_id, Product.shop_id == shop_id)
        .first()
    )
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy sản phẩm.")

    data = req.model_dump(exclude_unset=True)
    if "code" in data and data["code"]:
        data["code"] = data["code"].strip().upper()
    for k, v in data.items():
        setattr(product, k, v)

    db.commit()
    db.refresh(product)
    return ProductResponse.model_validate(product)


@api_router.get("/shops/{shop_id}/products/export/csv")
def export_products_csv(
    shop_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_shop_access(shop_id, current_user, db)
    products = db.query(Product).filter(Product.shop_id == shop_id).order_by(Product.code.asc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["code", "name", "unit_price", "stock_quantity", "is_active", "description"])
    for p in products:
        writer.writerow([p.code, p.name, p.unit_price, p.stock_quantity, p.is_active, p.description or ""])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="products_{shop_id}.csv"'},
    )


@api_router.post("/shops/{shop_id}/products/import/csv")
async def import_products_csv(
    shop_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    shop, _ = get_shop_access(shop_id, current_user, db)
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File vượt quá dung lượng 5MB.")

    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File CSV phải có bảng mã UTF-8.")

    reader = csv.DictReader(io.StringIO(decoded))
    created_count = 0
    updated_count = 0
    errors: List[str] = []

    for idx, row in enumerate(reader, start=2):
        code = (row.get("code") or "").strip().upper()
        name = (row.get("name") or "").strip()
        price_raw = (row.get("unit_price") or "").strip()
        stock_raw = (row.get("stock_quantity") or "0").strip()

        if not code or not name:
            errors.append(f"Dòng {idx}: Thiếu mã hoặc tên sản phẩm.")
            continue
        try:
            price = float(price_raw)
            stock = int(stock_raw or 0)
        except ValueError:
            errors.append(f"Dòng {idx}: Giá hoặc tồn kho không phải là số hợp lệ.")
            continue

        if price < 0 or stock < 0:
            errors.append(f"Dòng {idx}: Giá bán và số lượng tồn không được âm.")
            continue

        existing = db.query(Product).filter(Product.shop_id == shop.id, Product.code == code).first()
        if existing:
            existing.name = name
            existing.unit_price = price
            existing.stock_quantity = stock
            updated_count += 1
        else:
            db.add(
                Product(
                    shop_id=shop.id,
                    code=code,
                    name=name,
                    unit_price=price,
                    stock_quantity=stock,
                    description=(row.get("description") or "").strip() or None,
                    is_active=True,
                )
            )
            created_count += 1

    db.commit()
    return {
        "created": created_count,
        "updated": updated_count,
        "errors": errors,
    }


# ==============================================================================
# 7. COMMENTS & META WEBHOOK INGESTION (/shops/{shop_id}/comments, /webhooks/meta)
# ==============================================================================

def _ingest_single_comment(
    db: Session,
    shop: Shop,
    live_session: LiveSession,
    commenter_name: str,
    raw_message: str,
    external_comment_id: Optional[str] = None,
    commenter_external_id: Optional[str] = None,
    commenter_avatar: Optional[str] = None,
    commented_at: Optional[datetime] = None,
    external_page_id: Optional[str] = None,
) -> Comment:
    ext_cid = external_comment_id or f"cmt_{uuid.uuid4().hex[:14]}"

    # Deduplicate by (shop_id, external_comment_id)
    existing = (
        db.query(Comment)
        .filter(Comment.shop_id == shop.id, Comment.external_comment_id == ext_cid)
        .first()
    )
    if existing:
        return existing

    active_products = (
        db.query(Product)
        .filter(Product.shop_id == shop.id, Product.is_active == True)  # noqa: E712
        .all()
    )
    parsed = parse_livestream_comment(raw_message, active_products=active_products)

    status_val = CommentStatus.PARSED.value
    if parsed.is_ambiguous:
        status_val = CommentStatus.NEEDS_REVIEW.value

    comment = Comment(
        shop_id=shop.id,
        live_session_id=live_session.id,
        source_type=live_session.source_type,
        connection_mode=live_session.connection_mode,
        external_page_id=external_page_id,
        external_live_id=live_session.external_video_id,
        external_comment_id=ext_cid,
        commenter_external_id=commenter_external_id,
        commenter_name=commenter_name.strip(),
        commenter_avatar=commenter_avatar,
        raw_message=raw_message,  # Kept 100% intact
        parsed_product_code=parsed.product_code,
        parsed_quantity=parsed.quantity,
        parsed_color=parsed.color,
        parsed_size=parsed.size,
        parsed_intent=parsed.has_buy_intent,
        parse_confidence=parsed.confidence,
        missing_fields=",".join(parsed.missing_fields) if parsed.missing_fields else None,
        is_ambiguous=parsed.is_ambiguous,
        status=status_val,
        commented_at=commented_at or datetime.now(timezone.utc),
    )
    db.add(comment)
    db.flush()
    return comment


@api_router.post("/shops/{shop_id}/comments/parse-preview", response_model=CommentParseResult)
def preview_parse_comment(
    shop_id: str,
    req: CommentParsePreviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_shop_access(shop_id, current_user, db)
    active_products = (
        db.query(Product)
        .filter(Product.shop_id == shop_id, Product.is_active == True)  # noqa: E712
        .all()
    )
    return parse_livestream_comment(req.raw_message, active_products=active_products)


@api_router.post(
    "/shops/{shop_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_manual_or_mock_comment(
    shop_id: str,
    req: CommentManualCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    shop, _ = get_shop_access(shop_id, current_user, db)
    live_session = (
        db.query(LiveSession)
        .filter(LiveSession.id == req.live_session_id, LiveSession.shop_id == shop.id)
        .first()
    )
    if not live_session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiên livestream.")

    comment = _ingest_single_comment(
        db=db,
        shop=shop,
        live_session=live_session,
        commenter_name=req.commenter_name,
        raw_message=req.raw_message,
        external_comment_id=req.external_comment_id,
        commenter_external_id=req.commenter_external_id,
        commenter_avatar=req.commenter_avatar,
        commented_at=req.commented_at,
    )
    db.commit()
    db.refresh(comment)
    return CommentResponse.model_validate(comment)


@api_router.post("/shops/{shop_id}/comments/batch", response_model=List[CommentResponse])
def create_batch_manual_comments(
    shop_id: str,
    req: CommentBatchManualCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    shop, _ = get_shop_access(shop_id, current_user, db)
    live_session = (
        db.query(LiveSession)
        .filter(LiveSession.id == req.live_session_id, LiveSession.shop_id == shop.id)
        .first()
    )
    if not live_session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiên livestream.")

    results: List[Comment] = []
    for line in req.lines:
        c = _ingest_single_comment(
            db=db,
            shop=shop,
            live_session=live_session,
            commenter_name=line.commenter_name,
            raw_message=line.raw_message,
            external_comment_id=line.external_comment_id,
            commenter_external_id=line.commenter_external_id,
            commenter_avatar=line.commenter_avatar,
            commented_at=line.commented_at,
        )
        results.append(c)
    db.commit()
    return [CommentResponse.model_validate(c) for c in results]


@api_router.get("/shops/{shop_id}/comments", response_model=List[CommentResponse])
def list_comments(
    shop_id: str,
    live_session_id: Optional[str] = Query(None),
    source_type: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    q: Optional[str] = Query(None),
    sort: str = Query("asc", pattern="^(asc|desc)$"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Lists comments with search (customer name, product code, raw comment),
    filtering (source, live session, status), and sorting (default ascending by comment time
    to prioritize customers who commented first).
    """
    get_shop_access(shop_id, current_user, db)
    query = db.query(Comment).filter(Comment.shop_id == shop_id)

    if live_session_id:
        query = query.filter(Comment.live_session_id == live_session_id)
    if source_type:
        query = query.filter(Comment.source_type == source_type)
    if status_filter:
        query = query.filter(Comment.status == status_filter)
    if q and q.strip():
        kw = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Comment.commenter_name.ilike(kw),
                Comment.parsed_product_code.ilike(kw),
                Comment.raw_message.ilike(kw),
            )
        )

    order_clause = asc(Comment.commented_at) if sort == "asc" else desc(Comment.commented_at)
    comments = query.order_by(order_clause).offset(offset).limit(limit).all()
    return [CommentResponse.model_validate(c) for c in comments]


@api_router.get("/shops/{shop_id}/comments/{comment_id}", response_model=CommentResponse)
def get_comment_detail(
    shop_id: str,
    comment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_shop_access(shop_id, current_user, db)
    c = db.query(Comment).filter(Comment.id == comment_id, Comment.shop_id == shop_id).first()
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bình luận.")
    return CommentResponse.model_validate(c)


@api_router.get("/webhooks/meta", response_class=PlainTextResponse)
def verify_meta_webhook_challenge(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
):
    """
    Official Meta Webhook Verification Challenge endpoint.
    Ref: https://developers.facebook.com/docs/graph-api/webhooks/getting-started#verification-requests
    """
    if hub_mode == "subscribe" and hub_verify_token == settings.META_WEBHOOK_VERIFY_TOKEN:
        return PlainTextResponse(content=hub_challenge or "", status_code=status.HTTP_200_OK)
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Xác minh Webhook thất bại.")


@api_router.post("/webhooks/meta")
async def receive_meta_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Receives Meta Page feed/comment webhook events, verifies X-Hub-Signature-256,
    and performs idempotent comment ingestion so duplicate webhooks never create duplicate comments.
    """
    raw_body = await request.body()
    sig_header = request.headers.get("X-Hub-Signature-256")
    secret_to_use = settings.META_APP_SECRET or "dev_webhook_secret"

    if not verify_meta_webhook_signature(raw_body, sig_header, secret_to_use):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chữ ký X-Hub-Signature-256 không hợp lệ.",
        )

    payload = json.loads(raw_body.decode("utf-8"))
    payload_hash = hashlib.sha256(raw_body).hexdigest()

    ingested_comment_ids: List[str] = []
    duplicate_events = 0

    for entry in payload.get("data", payload.get("entry", [])):
        page_id = str(entry.get("id", ""))
        for change in entry.get("changes", []):
            val = change.get("value", {})
            if change.get("field") != "feed" or val.get("item") != "comment" or val.get("verb") != "add":
                continue

            ext_comment_id = str(val.get("comment_id", ""))
            if not ext_comment_id:
                continue

            # Idempotency check in webhook_events
            existing_event = (
                db.query(WebhookEvent)
                .filter(WebhookEvent.external_event_id == ext_comment_id)
                .first()
            )
            if existing_event:
                duplicate_events += 1
                continue

            # Find matching ConnectedAccount & active LiveSession
            conn_acc = (
                db.query(ConnectedAccount)
                .filter(ConnectedAccount.external_id == page_id)
                .first()
            )
            shop_id = conn_acc.shop_id if conn_acc else None
            wh_event = WebhookEvent(
                shop_id=shop_id,
                external_event_id=ext_comment_id,
                object_type="page_feed_comment",
                payload_hash=payload_hash,
                raw_payload=json.dumps(val, ensure_ascii=False),
                status="PROCESSED" if shop_id else "UNMATCHED_PAGE",
                processed_at=datetime.now(timezone.utc),
            )
            db.add(wh_event)
            db.flush()

            if conn_acc:
                shop = db.query(Shop).filter(Shop.id == conn_acc.shop_id).first()
                live_session = (
                    db.query(LiveSession)
                    .filter(
                        LiveSession.shop_id == conn_acc.shop_id,
                        LiveSession.status == LiveSessionStatus.LIVE.value,
                    )
                    .order_by(LiveSession.started_at.desc())
                    .first()
                )
                # Auto-create a LIVE session for this Fanpage if the shop owner forgot to open one
                if shop and not live_session:
                    live_session = LiveSession(
                        shop_id=shop.id,
                        connected_account_id=conn_acc.id,
                        external_video_id=str(val.get("post_id") or f"live_{uuid.uuid4().hex[:8]}"),
                        title=f"Live tự động: {conn_acc.name}",
                        source_type=SourcePlatform.FACEBOOK_PAGE.value,
                        connection_mode=conn_acc.connection_status,
                        status=LiveSessionStatus.LIVE.value,
                    )
                    db.add(live_session)
                    db.flush()
                if shop and live_session:
                    from_obj = val.get("from", {})
                    created_ts = val.get("created_time")
                    commented_dt = (
                        datetime.fromtimestamp(int(created_ts), tz=timezone.utc)
                        if created_ts
                        else datetime.now(timezone.utc)
                    )
                    c = _ingest_single_comment(
                        db=db,
                        shop=shop,
                        live_session=live_session,
                        commenter_name=from_obj.get("name", "Khách Facebook"),
                        raw_message=val.get("message", ""),
                        external_comment_id=ext_comment_id,
                        commenter_external_id=str(from_obj.get("id", "")) or None,
                        commented_at=commented_dt,
                        external_page_id=page_id,
                    )
                    ingested_comment_ids.append(c.id)

    db.commit()
    return {
        "status": "ok",
        "ingested_comments": len(ingested_comment_ids),
        "duplicate_events_ignored": duplicate_events,
    }


# ==============================================================================
# 8. ORDERS ("ĐÃ CHỐT" WORKFLOW, LIST, DETAIL, CANCEL)
# ==============================================================================

@api_router.post(
    "/shops/{shop_id}/orders/confirm",
    response_model=ConfirmOrderWorkflowResponse,
    status_code=status.HTTP_201_CREATED,
)
def confirm_order_endpoint(
    shop_id: str,
    req: ConfirmOrderFromCommentRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    shop, _ = get_shop_access(shop_id, current_user, db)
    client_ip = request.client.host if request.client else None
    return confirm_order_from_comment(
        db=db,
        shop=shop,
        user=current_user,
        req=req,
        ip_address=client_ip,
    )


@api_router.get("/shops/{shop_id}/orders", response_model=List[OrderResponse])
def list_orders(
    shop_id: str,
    live_session_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    q: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_shop_access(shop_id, current_user, db)
    query = db.query(Order).filter(Order.shop_id == shop_id)
    if live_session_id:
        query = query.filter(Order.live_session_id == live_session_id)
    if status_filter:
        query = query.filter(Order.status == status_filter)
    if q and q.strip():
        kw = f"%{q.strip()}%"
        query = query.filter(Order.order_code.ilike(kw))
    orders = query.order_by(Order.created_at.desc()).all()
    return [OrderResponse.model_validate(o) for o in orders]


@api_router.get("/shops/{shop_id}/orders/{order_id}", response_model=OrderResponse)
def get_order_detail(
    shop_id: str,
    order_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_shop_access(shop_id, current_user, db)
    order = db.query(Order).filter(Order.id == order_id, Order.shop_id == shop_id).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy đơn hàng.")
    return OrderResponse.model_validate(order)


@api_router.patch("/shops/{shop_id}/orders/{order_id}/status", response_model=OrderResponse)
def update_order_status(
    shop_id: str,
    order_id: str,
    req: OrderStatusUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    shop, _ = get_shop_access(shop_id, current_user, db)
    order = db.query(Order).filter(Order.id == order_id, Order.shop_id == shop_id).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy đơn hàng.")

    old_status = order.status
    order.status = req.status
    if req.notes is not None:
        order.notes = req.notes

    # If cancelled and comment was CONFIRMED, mark comment IGNORED so staff knows order was cancelled
    if req.status == OrderStatus.CANCELLED.value and order.comment_id:
        c = db.query(Comment).filter(Comment.id == order.comment_id).first()
        if c:
            c.status = CommentStatus.IGNORED.value

    db.add(
        AuditLog(
            shop_id=shop.id,
            user_id=current_user.id,
            action="ORDER_STATUS_CHANGED",
            entity_type="Order",
            entity_id=order.id,
            details=json.dumps(
                {"order_code": order.order_code, "from": old_status, "to": req.status},
                ensure_ascii=False,
            ),
        )
    )
    db.commit()
    db.refresh(order)
    return OrderResponse.model_validate(order)


# ==============================================================================
# 9. CUSTOMERS (/shops/{shop_id}/customers)
# ==============================================================================

@api_router.get("/shops/{shop_id}/customers")
def list_customers(
    shop_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_shop_access(shop_id, current_user, db)
    customers = (
        db.query(Customer)
        .filter(Customer.shop_id == shop_id)
        .order_by(Customer.created_at.desc())
        .all()
    )
    return [
        {
            "id": c.id,
            "display_name": c.display_name,
            "platform_user_id": c.platform_user_id,
            "customer_stt": c.customer_stt,
            "source_type": c.source_type,
            "phone": c.phone,
            "address": c.address,
            "created_at": c.created_at,
        }
        for c in customers
    ]


# ==============================================================================
# 10. MESSAGING LOGS & MANUAL ACTIONS (/shops/{shop_id}/messages)
# ==============================================================================

@api_router.get("/shops/{shop_id}/messages", response_model=List[MessageLogResponse])
def list_message_logs(
    shop_id: str,
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_shop_access(shop_id, current_user, db)
    query = db.query(MessageLog).filter(MessageLog.shop_id == shop_id)
    if status_filter:
        query = query.filter(MessageLog.status == status_filter)
    logs = query.order_by(MessageLog.created_at.desc()).all()
    return [MessageLogResponse.model_validate(m) for m in logs]


@api_router.post("/shops/{shop_id}/messages/{message_id}/mark-manual-sent", response_model=MessageLogResponse)
def mark_message_manually_sent(
    shop_id: str,
    message_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Explicitly called ONLY when staff confirms they actually pasted and sent the message
    inside Messenger. Simply copying or opening Messenger URL never calls this automatically.
    """
    shop, _ = get_shop_access(shop_id, current_user, db)
    log = db.query(MessageLog).filter(MessageLog.id == message_id, MessageLog.shop_id == shop.id).first()
    if not log:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bản ghi tin nhắn.")

    log.status = MessageStatus.SENT.value
    log.provider_mode = "MANUAL"
    log.sent_at = datetime.now(timezone.utc)
    db.add(
        AuditLog(
            shop_id=shop.id,
            user_id=current_user.id,
            action="MESSAGE_MANUALLY_CONFIRMED_SENT",
            entity_type="MessageLog",
            entity_id=log.id,
        )
    )
    db.commit()
    db.refresh(log)
    return MessageLogResponse.model_validate(log)


# ==============================================================================
# 11. PRINT JOBS (/shops/{shop_id}/print-jobs)
# ==============================================================================

@api_router.get("/shops/{shop_id}/print-jobs", response_model=List[PrintJobResponse])
def list_print_jobs(
    shop_id: str,
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_shop_access(shop_id, current_user, db)
    query = db.query(PrintJob).filter(PrintJob.shop_id == shop_id)
    if status_filter:
        query = query.filter(PrintJob.status == status_filter)
    jobs = query.order_by(PrintJob.created_at.desc()).all()
    return [PrintJobResponse.model_validate(j) for j in jobs]


@api_router.post("/shops/{shop_id}/orders/{order_id}/reprint", response_model=PrintJobResponse)
def reprint_order_receipt(
    shop_id: str,
    order_id: str,
    paper_size: Optional[str] = Query(None, pattern="^(80mm|A6|A5)$"),
    print_mode: str = Query("BROWSER", pattern="^(BROWSER|PRINT_BRIDGE)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    shop, _ = get_shop_access(shop_id, current_user, db)
    order = db.query(Order).filter(Order.id == order_id, Order.shop_id == shop.id).first()
    if not order or not order.items:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy đơn hàng để in lại.")

    customer = db.query(Customer).filter(Customer.id == order.customer_id).first()
    comment = db.query(Comment).filter(Comment.id == order.comment_id).first() if order.comment_id else None

    job = create_and_dispatch_print_job(
        db=db,
        shop=shop,
        order=order,
        customer=customer,
        first_item=order.items[0],
        comment=comment,
        print_mode=print_mode,
        paper_size=paper_size or shop.print_paper_size,
    )
    db.commit()
    db.refresh(job)
    return PrintJobResponse.model_validate(job)


@api_router.patch("/shops/{shop_id}/print-jobs/{job_id}/status", response_model=PrintJobResponse)
def update_print_job_status(
    shop_id: str,
    job_id: str,
    new_status: str = Query(..., pattern="^(QUEUED|PRINTING|PRINTED|FAILED|CANCELLED)$"),
    error_message: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Updates print job status. Opening browser print dialog sets PRINTING;
    only explicit user confirmation or print bridge ACK sets PRINTED.
    """
    get_shop_access(shop_id, current_user, db)
    job = db.query(PrintJob).filter(PrintJob.id == job_id, PrintJob.shop_id == shop_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lệnh in.")

    job.status = new_status
    if new_status == PrintJobStatus.PRINTED.value:
        job.printed_at = datetime.now(timezone.utc)
    if error_message is not None:
        job.error_message = error_message

    db.commit()
    db.refresh(job)
    return PrintJobResponse.model_validate(job)


# ==============================================================================
# 12. DASHBOARD METRICS (/shops/{shop_id}/dashboard)
# ==============================================================================

@api_router.get("/shops/{shop_id}/dashboard", response_model=DashboardMetricsResponse)
def get_dashboard_metrics(
    shop_id: str,
    live_session_id: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Computes accurate dashboard metrics with explicit definitions.
    - Unique confirmed customers are counted by distinct customer_id on non-cancelled orders (never by comment count).
    - Cancelled orders are excluded from confirmed revenue.
    """
    get_shop_access(shop_id, current_user, db)

    cmt_query = db.query(Comment).filter(Comment.shop_id == shop_id)
    ord_query = db.query(Order).filter(Order.shop_id == shop_id)
    msg_query = db.query(MessageLog).filter(MessageLog.shop_id == shop_id)
    prt_query = db.query(PrintJob).filter(PrintJob.shop_id == shop_id)

    if live_session_id:
        cmt_query = cmt_query.filter(Comment.live_session_id == live_session_id)
        ord_query = ord_query.filter(Order.live_session_id == live_session_id)

    total_comments = cmt_query.count()
    confirmed_comments = cmt_query.filter(Comment.status == CommentStatus.CONFIRMED.value).count()

    all_orders = ord_query.all()
    total_orders = len(all_orders)
    confirmed_orders = [o for o in all_orders if o.status == OrderStatus.CONFIRMED.value]
    pending_orders = len([o for o in all_orders if o.status == OrderStatus.PENDING_CONFIRMATION.value])
    cancelled_orders = len([o for o in all_orders if o.status == OrderStatus.CANCELLED.value])

    unique_confirmed_customers = len({o.customer_id for o in confirmed_orders})
    confirmed_revenue = round(sum(o.subtotal for o in confirmed_orders), 2)

    messages_sent = msg_query.filter(MessageLog.status == MessageStatus.SENT.value).count()
    messages_failed = msg_query.filter(MessageLog.status == MessageStatus.FAILED.value).count()
    messages_pending = msg_query.filter(
        MessageLog.status.in_(
            [
                MessageStatus.QUEUED.value,
                MessageStatus.SENDING.value,
                MessageStatus.NEEDS_MANUAL_ACTION.value,
            ]
        )
    ).count()

    prints_printed = prt_query.filter(PrintJob.status == PrintJobStatus.PRINTED.value).count()
    prints_failed = prt_query.filter(PrintJob.status == PrintJobStatus.FAILED.value).count()
    prints_queued = prt_query.filter(
        PrintJob.status.in_([PrintJobStatus.QUEUED.value, PrintJobStatus.PRINTING.value])
    ).count()

    return DashboardMetricsResponse(
        total_comments=total_comments,
        confirmed_comments=confirmed_comments,
        unique_confirmed_customers=unique_confirmed_customers,
        total_orders=total_orders,
        pending_orders=pending_orders,
        cancelled_orders=cancelled_orders,
        messages_sent=messages_sent,
        messages_failed=messages_failed,
        messages_pending_or_manual=messages_pending,
        prints_printed=prints_printed,
        prints_failed=prints_failed,
        prints_queued=prints_queued,
        confirmed_revenue=confirmed_revenue,
        metric_definitions={
            "unique_confirmed_customers": "Số khách hàng duy nhất (distinct customer_id) có ít nhất 1 đơn hàng ở trạng thái CONFIRMED. Không đếm trùng nhiều bình luận của cùng một khách.",
            "confirmed_revenue": "Tổng thành tiền của các đơn hàng ở trạng thái CONFIRMED. Không bao gồm đơn hàng đã hủy (CANCELLED) hoặc chờ xác nhận.",
        },
    )


# ==============================================================================
# 13. AUDIT LOGS (/shops/{shop_id}/audit-logs)
# ==============================================================================

@api_router.get("/shops/{shop_id}/audit-logs")
def list_audit_logs(
    shop_id: str,
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_shop_access(shop_id, current_user, db)
    logs = (
        db.query(AuditLog)
        .filter(AuditLog.shop_id == shop_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": l.id,
            "action": l.action,
            "entity_type": l.entity_type,
            "entity_id": l.entity_id,
            "user_id": l.user_id,
            "details": l.details,
            "ip_address": l.ip_address,
            "created_at": l.created_at,
        }
        for l in logs
    ]


# ==============================================================================
# 14. HEALTH CHECK & SYSTEM DIAGNOSTICS (/health)
# ==============================================================================

@api_router.get("/health")
def health_check(db: Session = Depends(get_db)):
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    return {
        "status": "healthy" if db_ok else "degraded",
        "app_env": settings.APP_ENV,
        "database_connected": db_ok,
        "database_dialect": db.bind.dialect.name if db.bind else "unknown",
        "meta_integration_mode": "REAL_CREDENTIALS_PRESENT"
        if settings.has_real_meta_credentials
        else ("DEMO_MOCK_ENABLED" if settings.allow_mock_provider else "BLOCKED_MISSING_CREDENTIALS"),
        "print_bridge_url": settings.PRINT_BRIDGE_URL,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
