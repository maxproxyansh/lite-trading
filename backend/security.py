from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from config import get_settings


pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
settings = get_settings()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def make_access_token(subject: str, role: str) -> tuple[str, int]:
    expires = utcnow() + timedelta(minutes=settings.access_token_minutes)
    payload = {"sub": subject, "role": role, "exp": expires}
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, settings.access_token_minutes * 60


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def make_refresh_token() -> tuple[str, datetime]:
    raw = secrets.token_urlsafe(48)
    expires = utcnow() + timedelta(days=settings.refresh_token_days)
    return raw, expires


def make_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def make_agent_secret() -> str:
    return f"lite_{secrets.token_urlsafe(24)}"


def key_prefix(secret: str) -> str:
    return secret[:12]
