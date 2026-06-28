"""Authentication routes for CineGen AI."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from auth_dependencies import get_current_user
from database import get_db
from db_models import User, utc_now
from models.saas import (
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
    UserPublic,
)
from services.auth_service import (
    AuthenticationError,
    authenticate_user,
    ensure_user_support_records,
    hash_password,
    issue_token_pair,
    revoke_refresh_token,
    rotate_refresh_token,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _public_user(user: User) -> UserPublic:
    return UserPublic(
        id=user.id,
        username=user.username,
        email=user.email,
        profile_picture=user.profile_picture,
        created_at=user.created_at,
        last_login=user.last_login,
        is_active=user.is_active,
        role=user.role,
    )


def _token_response(
    user: User,
    access_token: str,
    refresh_token: str,
    expires_in: int,
) -> TokenResponse:
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        user=_public_user(user),
    )


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user account",
)
async def register(
    request: RegisterRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Register a user and return an authenticated session."""
    email = request.email.lower()
    existing_user = db.scalar(
        select(User).where(
            or_(
                User.email == email,
                User.username == request.username,
            )
        )
    )
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email or username already exists.",
        )

    user = User(
        username=request.username,
        email=email,
        password_hash=hash_password(request.password),
        created_at=utc_now(),
        last_login=utc_now(),
        is_active=True,
        role="user",
    )
    db.add(user)
    db.flush()
    ensure_user_support_records(db, user)
    access_token, refresh_token, expires_in = issue_token_pair(
        db,
        user,
        remember_me=True,
    )
    return _token_response(user, access_token, refresh_token, expires_in)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Login with email and password",
)
async def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Authenticate a user from a JSON request."""
    user = authenticate_user(db, request.email, request.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    ensure_user_support_records(db, user)
    access_token, refresh_token, expires_in = issue_token_pair(
        db,
        user,
        remember_me=request.remember_me,
    )
    return _token_response(user, access_token, refresh_token, expires_in)


@router.post(
    "/token",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="OAuth2 password login",
)
async def token(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> TokenResponse:
    """OAuth2-compatible password flow using email as the username value."""
    user = authenticate_user(db, form.username, form.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    ensure_user_support_records(db, user)
    access_token, refresh_token, expires_in = issue_token_pair(db, user)
    return _token_response(user, access_token, refresh_token, expires_in)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh an access token",
)
async def refresh_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Rotate a refresh token and return a fresh token pair."""
    try:
        user, access_token, new_refresh_token, expires_in = rotate_refresh_token(
            db,
            request.refresh_token,
        )
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return _token_response(user, access_token, new_refresh_token, expires_in)


@router.post(
    "/logout",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Logout and revoke the refresh token",
)
async def logout(
    request: LogoutRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Logout the current user."""
    revoke_refresh_token(db, request.refresh_token)
    return MessageResponse(message=f"{current_user.username} logged out.")


@router.get(
    "/me",
    response_model=UserPublic,
    status_code=status.HTTP_200_OK,
    summary="Return the authenticated user",
)
async def me(current_user: User = Depends(get_current_user)) -> UserPublic:
    """Return the current user profile."""
    return _public_user(current_user)


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Start password reset flow",
)
async def forgot_password(
    request: ForgotPasswordRequest,
) -> MessageResponse:
    """Return a safe password reset message without exposing account existence."""
    return MessageResponse(
        message=(
            "If an account exists for "
            f"{request.email}, password reset instructions will be sent."
        )
    )
