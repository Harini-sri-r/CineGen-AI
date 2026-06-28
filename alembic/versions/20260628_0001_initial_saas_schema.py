"""Initial SaaS schema."""

from alembic import op
import sqlalchemy as sa

revision = "20260628_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("profile_picture", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_login", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    op.create_table(
        "stories",
        sa.Column("story_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("story", sa.Text(), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("target_duration_seconds", sa.Integer(), nullable=True),
        sa.Column("generation_duration_seconds", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("story_id"),
        sa.UniqueConstraint("user_id", "file_name", name="uq_user_story_file"),
    )
    op.create_index(op.f("ix_stories_created_at"), "stories", ["created_at"], unique=False)
    op.create_index(op.f("ix_stories_file_name"), "stories", ["file_name"], unique=False)
    op.create_index(op.f("ix_stories_status"), "stories", ["status"], unique=False)
    op.create_index(op.f("ix_stories_story_id"), "stories", ["story_id"], unique=False)
    op.create_index(op.f("ix_stories_user_id"), "stories", ["user_id"], unique=False)

    op.create_table(
        "refresh_tokens",
        sa.Column("token_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("token_id"),
    )
    op.create_index(op.f("ix_refresh_tokens_expires_at"), "refresh_tokens", ["expires_at"], unique=False)
    op.create_index(op.f("ix_refresh_tokens_token_hash"), "refresh_tokens", ["token_hash"], unique=True)
    op.create_index(op.f("ix_refresh_tokens_token_id"), "refresh_tokens", ["token_id"], unique=False)
    op.create_index(op.f("ix_refresh_tokens_user_id"), "refresh_tokens", ["user_id"], unique=False)

    op.create_table(
        "statistics",
        sa.Column("stat_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("total_stories", sa.Integer(), nullable=False),
        sa.Column("total_images", sa.Integer(), nullable=False),
        sa.Column("total_videos", sa.Integer(), nullable=False),
        sa.Column("total_generation_seconds", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("stat_id"),
    )
    op.create_index(op.f("ix_statistics_stat_id"), "statistics", ["stat_id"], unique=False)
    op.create_index(op.f("ix_statistics_user_id"), "statistics", ["user_id"], unique=True)

    op.create_table(
        "user_settings",
        sa.Column("setting_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("theme", sa.String(length=40), nullable=False),
        sa.Column("language", sa.String(length=20), nullable=False),
        sa.Column("voice_selection", sa.String(length=120), nullable=False),
        sa.Column("image_provider", sa.String(length=80), nullable=False),
        sa.Column("background_music_enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("setting_id"),
    )
    op.create_index(op.f("ix_user_settings_setting_id"), "user_settings", ["setting_id"], unique=False)
    op.create_index(op.f("ix_user_settings_user_id"), "user_settings", ["user_id"], unique=True)

    op.create_table(
        "scenes",
        sa.Column("scene_id", sa.Integer(), nullable=False),
        sa.Column("story_id", sa.Integer(), nullable=False),
        sa.Column("scene_number", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["story_id"], ["stories.story_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("scene_id"),
        sa.UniqueConstraint("story_id", "scene_number", name="uq_story_scene_number"),
    )
    op.create_index(op.f("ix_scenes_scene_id"), "scenes", ["scene_id"], unique=False)
    op.create_index(op.f("ix_scenes_story_id"), "scenes", ["story_id"], unique=False)

    op.create_table(
        "generation_history",
        sa.Column("history_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("story_id", sa.Integer(), nullable=False),
        sa.Column("generation_time", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.ForeignKeyConstraint(["story_id"], ["stories.story_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("history_id"),
    )
    op.create_index(op.f("ix_generation_history_generation_time"), "generation_history", ["generation_time"], unique=False)
    op.create_index(op.f("ix_generation_history_history_id"), "generation_history", ["history_id"], unique=False)
    op.create_index(op.f("ix_generation_history_story_id"), "generation_history", ["story_id"], unique=False)
    op.create_index(op.f("ix_generation_history_user_id"), "generation_history", ["user_id"], unique=False)

    op.create_table(
        "videos",
        sa.Column("video_id", sa.Integer(), nullable=False),
        sa.Column("story_id", sa.Integer(), nullable=False),
        sa.Column("video_url", sa.String(length=1000), nullable=True),
        sa.Column("video_path", sa.String(length=1000), nullable=True),
        sa.Column("thumbnail_url", sa.String(length=1000), nullable=True),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["story_id"], ["stories.story_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("video_id"),
    )
    op.create_index(op.f("ix_videos_story_id"), "videos", ["story_id"], unique=False)
    op.create_index(op.f("ix_videos_video_id"), "videos", ["video_id"], unique=False)

    op.create_table(
        "prompts",
        sa.Column("prompt_id", sa.Integer(), nullable=False),
        sa.Column("scene_id", sa.Integer(), nullable=False),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["scene_id"], ["scenes.scene_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("prompt_id"),
    )
    op.create_index(op.f("ix_prompts_prompt_id"), "prompts", ["prompt_id"], unique=False)
    op.create_index(op.f("ix_prompts_scene_id"), "prompts", ["scene_id"], unique=True)

    op.create_table(
        "images",
        sa.Column("image_id", sa.Integer(), nullable=False),
        sa.Column("scene_id", sa.Integer(), nullable=False),
        sa.Column("image_url", sa.String(length=1000), nullable=True),
        sa.Column("image_path", sa.String(length=1000), nullable=True),
        sa.Column("provider", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("warning", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["scene_id"], ["scenes.scene_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("image_id"),
    )
    op.create_index(op.f("ix_images_created_at"), "images", ["created_at"], unique=False)
    op.create_index(op.f("ix_images_image_id"), "images", ["image_id"], unique=False)
    op.create_index(op.f("ix_images_scene_id"), "images", ["scene_id"], unique=False)

    op.create_table(
        "audio",
        sa.Column("audio_id", sa.Integer(), nullable=False),
        sa.Column("scene_id", sa.Integer(), nullable=False),
        sa.Column("audio_url", sa.String(length=1000), nullable=True),
        sa.Column("audio_path", sa.String(length=1000), nullable=True),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["scene_id"], ["scenes.scene_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("audio_id"),
    )
    op.create_index(op.f("ix_audio_audio_id"), "audio", ["audio_id"], unique=False)
    op.create_index(op.f("ix_audio_scene_id"), "audio", ["scene_id"], unique=False)


def downgrade() -> None:
    op.drop_table("audio")
    op.drop_table("images")
    op.drop_table("prompts")
    op.drop_table("videos")
    op.drop_table("generation_history")
    op.drop_table("scenes")
    op.drop_table("user_settings")
    op.drop_table("statistics")
    op.drop_table("refresh_tokens")
    op.drop_table("stories")
    op.drop_table("users")
