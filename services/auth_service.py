"""Authentication helpers for CineGen AI."""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

import bcrypt
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from db_models import RefreshToken, User, UserSettings, Statistics, utc_now

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-for-production-cinegen-ai")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "14"))
REMEMBER_REFRESH_TOKEN_EXPIRE_DAYS = int(
    os.getenv("JWT_REMEMBER_REFRESH_TOKEN_EXPIRE_DAYS", "30")
)


class AuthenticationError(RuntimeError):
    """Raised when credentials or tokens are invalid."""


def hash_password(password: str) -> str:
    """Hash a password with bcrypt."""
    password_bytes = password.encode("utf-8")
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Return true when the submitted password matches the stored hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def hash_token(token: str) -> str:
    """Hash a refresh token before storing it."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(user: User) -> tuple[str, int]:
    """Create a signed access token and its lifetime in seconds."""
    expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    expires_at = datetime.utcnow() + expires_delta
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "type": "access",
        "exp": expires_at,
        "iat": datetime.utcnow(),
        "jti": str(uuid4()),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM), int(
        expires_delta.total_seconds()
    )


def create_refresh_token(db: Session, user: User, remember_me: bool = False) -> str:
    """Create and store a refresh token."""
    expire_days = (
        REMEMBER_REFRESH_TOKEN_EXPIRE_DAYS if remember_me else REFRESH_TOKEN_EXPIRE_DAYS
    )
    expires_at = datetime.utcnow() + timedelta(days=expire_days)
    payload = {
        "sub": str(user.id),
        "type": "refresh",
        "exp": expires_at,
        "iat": datetime.utcnow(),
        "jti": str(uuid4()),
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=expires_at,
        )
    )
    return token


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    """Decode a JWT and verify its declared token type."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except JWTError as exc:
        raise AuthenticationError("Invalid or expired token.") from exc

    if payload.get("type") != expected_type:
        raise AuthenticationError("Invalid token type.")

    if not payload.get("sub"):
        raise AuthenticationError("Token subject is missing.")

    return payload


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Return the active user for valid credentials."""
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None or not user.is_active:
        return None

    if not verify_password(password, user.password_hash):
        return None

    user.last_login = utc_now()
    return user


def issue_token_pair(
    db: Session,
    user: User,
    remember_me: bool = False,
) -> tuple[str, str, int]:
    """Create an access/refresh token pair and persist the refresh token."""
    access_token, expires_in = create_access_token(user)
    refresh_token = create_refresh_token(db, user, remember_me=remember_me)
    db.commit()
    db.refresh(user)
    return access_token, refresh_token, expires_in


def rotate_refresh_token(db: Session, refresh_token: str) -> tuple[User, str, str, int]:
    """Validate, revoke, and replace a refresh token."""
    payload = decode_token(refresh_token, expected_type="refresh")
    token_record = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(refresh_token))
    )
    if (
        token_record is None
        or token_record.revoked_at is not None
        or token_record.expires_at <= datetime.utcnow()
    ):
        raise AuthenticationError("Refresh token is invalid or expired.")

    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise AuthenticationError("User account is inactive.")

    token_record.revoked_at = utc_now()
    access_token, expires_in = create_access_token(user)
    new_refresh_token = create_refresh_token(db, user)
    db.commit()
    db.refresh(user)
    return user, access_token, new_refresh_token, expires_in


def revoke_refresh_token(db: Session, refresh_token: str | None) -> None:
    """Revoke a refresh token when present."""
    if not refresh_token:
        return

    token_record = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(refresh_token))
    )
    if token_record and token_record.revoked_at is None:
        token_record.revoked_at = utc_now()
        db.commit()


def ensure_user_support_records(db: Session, user: User) -> None:
    """Create settings/statistics rows for a new or imported user."""
    if user.settings is None:
        db.add(UserSettings(user_id=user.id))
    if user.statistics is None:
        db.add(Statistics(user_id=user.id))
