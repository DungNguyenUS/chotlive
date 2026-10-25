from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
import jwt
from cryptography.fernet import Fernet

from app.core.config import settings


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def create_access_token(
    subject: str,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    payload: Dict[str, Any] = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def decode_access_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])


def encrypt_secret(plaintext: str) -> str:
    if not plaintext:
        return ""
    f = Fernet(settings.fernet_key)
    return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    f = Fernet(settings.fernet_key)
    return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")


def verify_meta_webhook_signature(raw_body: bytes, signature_header: Optional[str], app_secret: str) -> bool:
    """
    Verify X-Hub-Signature-256 sent by Meta Webhooks.
    Header format: sha256=<hex_digest>
    Ref: https://developers.facebook.com/docs/graph-api/webhooks/getting-started#Event-Notifications
    """
    if not signature_header or not signature_header.startswith("sha256=") or not app_secret:
        return False
    received_sig = signature_header.split("sha256=", 1)[1].strip()
    expected_sig = hmac.new(
        key=app_secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(received_sig, expected_sig)
