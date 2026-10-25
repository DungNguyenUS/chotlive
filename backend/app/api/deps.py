from __future__ import annotations

import time
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models import Shop, ShopMember, ShopRole, User

bearer_scheme = HTTPBearer(auto_error=False)

# In-memory sliding window rate limiter per client IP / key
_RATE_BUCKETS: Dict[str, List[float]] = defaultdict(list)


def reset_rate_limiter() -> None:
    _RATE_BUCKETS.clear()


def enforce_rate_limit(request: Request) -> None:
    client_ip = request.client.host if request.client else "127.0.0.1"
    custom_limit = request.headers.get("X-Test-Rate-Limit")
    limit = settings.RATE_LIMIT_REQUESTS_PER_MINUTE
    if custom_limit and not settings.is_production:
        try:
            limit = int(custom_limit)
        except ValueError:
            pass

    now = time.time()
    window_start = now - 60.0
    bucket_key = f"{client_ip}:{request.url.path}"
    history = [ts for ts in _RATE_BUCKETS[bucket_key] if ts > window_start]
    if len(history) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Quá nhiều yêu cầu trong thời gian ngắn (Rate limit exceeded). Vui lòng thử lại sau.",
        )
    history.append(now)
    _RATE_BUCKETS[bucket_key] = history


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Vui lòng đăng nhập để tiếp tục.",
        )
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = payload.get("sub")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Phiên đăng nhập không hợp lệ hoặc đã hết hạn.",
        )

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()  # noqa: E712
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản không tồn tại hoặc đã bị khóa.",
        )
    return user


def get_shop_access(
    shop_id: str,
    user: User,
    db: Session,
    required_roles: Optional[List[str]] = None,
) -> Tuple[Shop, ShopMember]:
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy cửa hàng.",
        )
    member = (
        db.query(ShopMember)
        .filter(
            ShopMember.shop_id == shop_id,
            ShopMember.user_id == user.id,
            ShopMember.is_active == True,  # noqa: E712
        )
        .first()
    )
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền truy cập vào dữ liệu của cửa hàng này.",
        )
    if required_roles and member.role not in required_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Thao tác này yêu cầu quyền {', '.join(required_roles)}.",
        )
    return shop, member
