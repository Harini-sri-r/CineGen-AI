"""Pydantic schemas for CineGen AI SaaS APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from models.story import AudioResponse, ImageResponse, Prompt, Scene


class UserPublic(BaseModel):
    """Safe user profile returned to the frontend."""

    id: int
    username: str
    email: EmailStr
    profile_picture: str | None = None
    created_at: datetime
    last_login: datetime | None = None
    is_active: bool
    role: str = "user"


class RegisterRequest(BaseModel):
    """Registration request."""

    username: str = Field(..., min_length=3, max_length=80)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        username = " ".join(value.split()).strip()
        if not username:
            raise ValueError("Username is required.")
        return username


class LoginRequest(BaseModel):
    """Email/password login request."""

    email: EmailStr
    password: str = Field(..., min_length=1)
    remember_me: bool = False


class TokenResponse(BaseModel):
    """JWT token pair response."""

    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserPublic


class RefreshTokenRequest(BaseModel):
    """Refresh-token rotation request."""

    refresh_token: str = Field(..., min_length=1)


class LogoutRequest(BaseModel):
    """Logout request."""

    refresh_token: str | None = None


class ForgotPasswordRequest(BaseModel):
    """Forgot-password request."""

    email: EmailStr


class MessageResponse(BaseModel):
    """Generic success message."""

    success: bool = True
    message: str


class ProfileUpdateRequest(BaseModel):
    """Profile update request."""

    username: str | None = Field(default=None, min_length=3, max_length=80)
    email: EmailStr | None = None
    profile_picture: str | None = Field(default=None, max_length=500)


class PasswordChangeRequest(BaseModel):
    """Password change request."""

    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)


class UserSettingsResponse(BaseModel):
    """Settings returned for one user."""

    theme: Literal["dark", "light"] = "light"
    language: str = "en"
    voice_selection: str = "en-US-GuyNeural"
    image_provider: str = "pollinations"
    background_music_enabled: bool = True


class UserSettingsUpdateRequest(BaseModel):
    """Settings update request."""

    theme: Literal["dark", "light"] | None = None
    language: str | None = Field(default=None, min_length=2, max_length=20)
    voice_selection: str | None = Field(default=None, min_length=1, max_length=120)
    image_provider: str | None = Field(default=None, min_length=1, max_length=80)
    background_music_enabled: bool | None = None


class DashboardStats(BaseModel):
    """Dashboard aggregate counters."""

    total_stories: int = 0
    total_images: int = 0
    total_videos: int = 0
    total_scenes: int = 0
    generation_seconds: float = 0.0


class HistoryCard(BaseModel):
    """Card-friendly generation summary."""

    story_id: int
    file_name: str | None = None
    title: str
    created_at: datetime
    generation_time: datetime
    status: str
    thumbnail_url: str | None = None
    images_count: int = 0
    video_duration: float | None = None
    video_url: str | None = None


class DashboardResponse(BaseModel):
    """Dashboard payload."""

    user: UserPublic
    stats: DashboardStats
    recent_stories: list[HistoryCard]
    latest_activity: list[HistoryCard]


class PaginatedHistoryResponse(BaseModel):
    """Paginated history response."""

    items: list[HistoryCard]
    total: int
    page: int
    page_size: int
    pages: int


class StoryDetailResponse(BaseModel):
    """Full user-owned story detail."""

    story_id: int
    file_name: str | None = None
    title: str
    story: str
    created_at: datetime
    status: str
    target_duration_seconds: int | None = None
    generation_duration_seconds: float | None = None
    scenes: list[Scene]
    prompts: list[Prompt]
    images: list[ImageResponse]
    audio: list[AudioResponse] = Field(default_factory=list)
    video_path: str | None = None
    video_url: str | None = None
    thumbnail_url: str | None = None
    video_duration_seconds: float | None = None


class ImageLibraryItem(BaseModel):
    """Image library item."""

    image_id: int
    story_id: int
    scene_number: int
    title: str
    prompt: str | None = None
    image_url: str | None = None
    image_path: str | None = None
    provider: str | None = None
    status: str
    created_at: datetime


class ImageLibraryResponse(BaseModel):
    """Image library response."""

    items: list[ImageLibraryItem]
    total: int


class VideoLibraryItem(BaseModel):
    """Video library item."""

    video_id: int
    story_id: int
    title: str
    video_url: str | None = None
    video_path: str | None = None
    thumbnail_url: str | None = None
    duration: float | None = None
    created_at: datetime


class VideoLibraryResponse(BaseModel):
    """Video library response."""

    items: list[VideoLibraryItem]
    total: int


class ProfileResponse(BaseModel):
    """Profile page payload."""

    user: UserPublic
    stats: DashboardStats
    settings: UserSettingsResponse
