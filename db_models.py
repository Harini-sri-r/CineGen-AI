"""SQLAlchemy models for the CineGen AI SaaS data model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def utc_now() -> datetime:
    """Return a naive UTC timestamp for database portability."""
    return datetime.utcnow()


class User(Base):
    """Registered CineGen AI account."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    profile_picture: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    role: Mapped[str] = mapped_column(String(40), default="user")

    stories: Mapped[list[Story]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    generation_history: Mapped[list[GenerationHistory]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    statistics: Mapped[Statistics | None] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
        passive_deletes=True,
    )
    settings: Mapped[UserSettings | None] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
        passive_deletes=True,
    )
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Story(Base):
    """A user-owned story generation."""

    __tablename__ = "stories"
    __table_args__ = (UniqueConstraint("user_id", "file_name", name="uq_user_story_file"),)

    story_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    story: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(String(180), default="Untitled story")
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    status: Mapped[str] = mapped_column(String(40), default="completed", index=True)
    target_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    generation_duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    user: Mapped[User] = relationship(back_populates="stories")
    scenes: Mapped[list[Scene]] = relationship(
        back_populates="story",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Scene.scene_number",
    )
    videos: Mapped[list[Video]] = relationship(
        back_populates="story",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    history_items: Mapped[list[GenerationHistory]] = relationship(
        back_populates="story",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Scene(Base):
    """One extracted scene in a story."""

    __tablename__ = "scenes"
    __table_args__ = (
        UniqueConstraint("story_id", "scene_number", name="uq_story_scene_number"),
    )

    scene_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    story_id: Mapped[int] = mapped_column(
        ForeignKey("stories.story_id", ondelete="CASCADE"),
        index=True,
    )
    scene_number: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text)

    story: Mapped[Story] = relationship(back_populates="scenes")
    prompt: Mapped[Prompt | None] = relationship(
        back_populates="scene",
        cascade="all, delete-orphan",
        uselist=False,
        passive_deletes=True,
    )
    images: Mapped[list[Image]] = relationship(
        back_populates="scene",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    audio: Mapped[list[Audio]] = relationship(
        back_populates="scene",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Prompt(Base):
    """Generated visual prompt for a scene."""

    __tablename__ = "prompts"

    prompt_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    scene_id: Mapped[int] = mapped_column(
        ForeignKey("scenes.scene_id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    prompt_text: Mapped[str] = mapped_column(Text)

    scene: Mapped[Scene] = relationship(back_populates="prompt")


class Image(Base):
    """Generated image metadata for a scene."""

    __tablename__ = "images"

    image_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    scene_id: Mapped[int] = mapped_column(
        ForeignKey("scenes.scene_id", ondelete="CASCADE"),
        index=True,
    )
    image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    image_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="success")
    warning: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)

    scene: Mapped[Scene] = relationship(back_populates="images")


class Audio(Base):
    """Generated narration metadata for a scene."""

    __tablename__ = "audio"

    audio_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    scene_id: Mapped[int] = mapped_column(
        ForeignKey("scenes.scene_id", ondelete="CASCADE"),
        index=True,
    )
    audio_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    audio_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="success")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    scene: Mapped[Scene] = relationship(back_populates="audio")


class Video(Base):
    """Generated MP4 metadata for a story."""

    __tablename__ = "videos"

    video_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    story_id: Mapped[int] = mapped_column(
        ForeignKey("stories.story_id", ondelete="CASCADE"),
        index=True,
    )
    video_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    video_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)

    story: Mapped[Story] = relationship(back_populates="videos")


class GenerationHistory(Base):
    """A user-facing history row for a generation."""

    __tablename__ = "generation_history"

    history_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    story_id: Mapped[int] = mapped_column(
        ForeignKey("stories.story_id", ondelete="CASCADE"),
        index=True,
    )
    generation_time: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    status: Mapped[str] = mapped_column(String(40), default="completed")

    user: Mapped[User] = relationship(back_populates="generation_history")
    story: Mapped[Story] = relationship(back_populates="history_items")


class Statistics(Base):
    """Cached aggregate counters for one user."""

    __tablename__ = "statistics"

    stat_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    total_stories: Mapped[int] = mapped_column(Integer, default=0)
    total_images: Mapped[int] = mapped_column(Integer, default=0)
    total_videos: Mapped[int] = mapped_column(Integer, default=0)
    total_generation_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    user: Mapped[User] = relationship(back_populates="statistics")


class UserSettings(Base):
    """Per-user product preferences."""

    __tablename__ = "user_settings"

    setting_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    theme: Mapped[str] = mapped_column(String(40), default="light")
    language: Mapped[str] = mapped_column(String(20), default="en")
    voice_selection: Mapped[str] = mapped_column(String(120), default="en-US-GuyNeural")
    image_provider: Mapped[str] = mapped_column(String(80), default="pollinations")
    background_music_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    user: Mapped[User] = relationship(back_populates="settings")


class RefreshToken(Base):
    """Persisted refresh token hash for logout and rotation."""

    __tablename__ = "refresh_tokens"

    token_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship(back_populates="refresh_tokens")
