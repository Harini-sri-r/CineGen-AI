"""Database persistence and query helpers for CineGen AI SaaS features."""

from __future__ import annotations

from math import ceil
from pathlib import Path

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session, selectinload

from db_models import (
    Audio as AudioRecord,
    GenerationHistory,
    Image as ImageRecord,
    Prompt as PromptRecord,
    Scene as SceneRecord,
    Statistics,
    Story,
    User,
    UserSettings,
    Video as VideoRecord,
    utc_now,
)
from models.saas import (
    DashboardResponse,
    DashboardStats,
    HistoryCard,
    ImageLibraryItem,
    PaginatedHistoryResponse,
    ProfileResponse,
    StoryDetailResponse,
    UserPublic,
    UserSettingsResponse,
    VideoLibraryItem,
)
from models.story import AudioResponse, HistoryDetail, ImageResponse, Prompt, Scene


def story_title(story: str) -> str:
    """Build a compact display title from story text."""
    cleaned = " ".join(story.split()).strip()
    if not cleaned:
        return "Untitled story"

    first_sentence = cleaned.split(".", 1)[0].strip()
    title = first_sentence or cleaned
    if len(title) > 120:
        return f"{title[:117].rstrip()}..."

    return title


def ensure_user_rows(db: Session, user: User) -> None:
    """Ensure profile support rows exist."""
    if user.settings is None:
        db.add(UserSettings(user_id=user.id))
    if user.statistics is None:
        db.add(Statistics(user_id=user.id))
    db.flush()


def persist_story_generation(
    db: Session,
    user: User,
    file_name: str | None,
    story: str,
    scenes: list[Scene],
    prompts: list[Prompt],
    images: list[ImageResponse],
    audio: list[AudioResponse] | None = None,
    video_path: str | None = None,
    video_url: str | None = None,
    thumbnail_url: str | None = None,
    video_duration_seconds: float | None = None,
    target_duration_seconds: int | None = None,
    generation_duration_seconds: float | None = None,
    status: str = "completed",
) -> Story:
    """Create or replace the database metadata for one generated story."""
    ensure_user_rows(db, user)
    story_record = _get_story_by_file_name(db, user, file_name)

    if story_record is None:
        story_record = Story(
            user_id=user.id,
            story=story,
            title=story_title(story),
            file_name=file_name,
            status=status,
            target_duration_seconds=target_duration_seconds,
            generation_duration_seconds=generation_duration_seconds,
        )
        db.add(story_record)
        db.flush()
    else:
        story_record.story = story
        story_record.title = story_title(story)
        story_record.status = status
        story_record.target_duration_seconds = target_duration_seconds
        story_record.generation_duration_seconds = generation_duration_seconds
        _clear_story_children(db, story_record)

    scene_records = _persist_scenes(db, story_record, scenes)
    _persist_prompts(db, scene_records, prompts)
    _persist_images(db, scene_records, images)
    _persist_audio(db, scene_records, audio or [])
    if video_path or video_url:
        db.add(
            VideoRecord(
                story_id=story_record.story_id,
                video_path=video_path,
                video_url=video_url or video_path,
                thumbnail_url=thumbnail_url,
                duration=video_duration_seconds,
            )
        )

    history_item = db.scalar(
        select(GenerationHistory).where(
            GenerationHistory.user_id == user.id,
            GenerationHistory.story_id == story_record.story_id,
        )
    )
    if history_item is None:
        db.add(
            GenerationHistory(
                user_id=user.id,
                story_id=story_record.story_id,
                status=status,
            )
        )
    else:
        history_item.status = status
        history_item.generation_time = utc_now()

    refresh_user_statistics(db, user.id)
    db.commit()
    db.refresh(story_record)
    return story_record


def update_story_image_metadata(
    db: Session,
    user: User,
    file_name: str,
    image: ImageResponse,
) -> None:
    """Update one saved scene image for a user-owned story."""
    story_record = db.scalar(
        select(Story)
        .where(Story.user_id == user.id, Story.file_name == file_name)
        .options(selectinload(Story.scenes).selectinload(SceneRecord.images))
    )
    if story_record is None:
        return

    scene_record = next(
        (scene for scene in story_record.scenes if scene.scene_number == image.scene),
        None,
    )
    if scene_record is None:
        return

    for existing_image in list(scene_record.images):
        db.delete(existing_image)

    db.add(
        ImageRecord(
            scene_id=scene_record.scene_id,
            image_url=image.image_url,
            image_path=image.image_path,
            provider=image.provider,
            status=image.status,
            warning=image.warning,
            error=image.error,
        )
    )
    story_record.status = "partial" if image.status == "failed" else story_record.status
    refresh_user_statistics(db, user.id)
    db.commit()


def _get_story_by_file_name(
    db: Session,
    user: User,
    file_name: str | None,
) -> Story | None:
    if not file_name:
        return None

    return db.scalar(
        select(Story)
        .where(Story.user_id == user.id, Story.file_name == file_name)
        .options(selectinload(Story.scenes), selectinload(Story.videos))
    )


def _clear_story_children(db: Session, story_record: Story) -> None:
    scene_ids = [
        scene_id
        for scene_id in db.scalars(
            select(SceneRecord.scene_id).where(
                SceneRecord.story_id == story_record.story_id
            )
        ).all()
    ]
    if scene_ids:
        db.execute(delete(PromptRecord).where(PromptRecord.scene_id.in_(scene_ids)))
        db.execute(delete(ImageRecord).where(ImageRecord.scene_id.in_(scene_ids)))
        db.execute(delete(AudioRecord).where(AudioRecord.scene_id.in_(scene_ids)))
    db.execute(
        delete(SceneRecord).where(SceneRecord.story_id == story_record.story_id)
    )
    db.execute(
        delete(VideoRecord).where(VideoRecord.story_id == story_record.story_id)
    )
    db.flush()


def _persist_scenes(
    db: Session,
    story_record: Story,
    scenes: list[Scene],
) -> dict[int, SceneRecord]:
    scene_records: dict[int, SceneRecord] = {}
    for scene in scenes:
        scene_record = SceneRecord(
            story_id=story_record.story_id,
            scene_number=scene.scene,
            description=scene.description,
        )
        db.add(scene_record)
        db.flush()
        scene_records[scene.scene] = scene_record

    return scene_records


def _persist_prompts(
    db: Session,
    scene_records: dict[int, SceneRecord],
    prompts: list[Prompt],
) -> None:
    for prompt in prompts:
        scene_record = scene_records.get(prompt.scene)
        if scene_record is None:
            continue

        db.add(PromptRecord(scene_id=scene_record.scene_id, prompt_text=prompt.prompt))


def _persist_images(
    db: Session,
    scene_records: dict[int, SceneRecord],
    images: list[ImageResponse],
) -> None:
    for image in images:
        scene_record = scene_records.get(image.scene)
        if scene_record is None:
            continue

        db.add(
            ImageRecord(
                scene_id=scene_record.scene_id,
                image_url=image.image_url,
                image_path=image.image_path,
                provider=image.provider,
                status=image.status,
                warning=image.warning,
                error=image.error,
            )
        )


def _persist_audio(
    db: Session,
    scene_records: dict[int, SceneRecord],
    audio: list[AudioResponse],
) -> None:
    for audio_item in audio:
        scene_record = scene_records.get(audio_item.scene)
        if scene_record is None:
            continue

        db.add(
            AudioRecord(
                scene_id=scene_record.scene_id,
                audio_url=audio_item.audio_url,
                audio_path=audio_item.audio_path,
                duration=audio_item.duration_seconds,
                status=audio_item.status,
                error=audio_item.error,
            )
        )


def refresh_user_statistics(db: Session, user_id: int) -> Statistics:
    """Refresh cached user statistics from source tables."""
    stats = db.scalar(select(Statistics).where(Statistics.user_id == user_id))
    if stats is None:
        stats = Statistics(user_id=user_id)
        db.add(stats)
        db.flush()

    story_ids = select(Story.story_id).where(Story.user_id == user_id)
    stats.total_stories = db.scalar(
        select(func.count()).select_from(Story).where(Story.user_id == user_id)
    ) or 0
    stats.total_images = db.scalar(
        select(func.count())
        .select_from(ImageRecord)
        .join(SceneRecord)
        .where(
            SceneRecord.story_id.in_(story_ids),
            ImageRecord.status == "success",
        )
    ) or 0
    stats.total_videos = db.scalar(
        select(func.count())
        .select_from(VideoRecord)
        .where(VideoRecord.story_id.in_(story_ids))
    ) or 0
    stats.total_generation_seconds = db.scalar(
        select(func.coalesce(func.sum(Story.generation_duration_seconds), 0.0)).where(
            Story.user_id == user_id
        )
    ) or 0.0
    stats.updated_at = utc_now()
    return stats


def dashboard_stats(db: Session, user_id: int) -> DashboardStats:
    """Build live dashboard statistics."""
    stats = refresh_user_statistics(db, user_id)
    story_ids = select(Story.story_id).where(Story.user_id == user_id)
    total_scenes = db.scalar(
        select(func.count())
        .select_from(SceneRecord)
        .where(SceneRecord.story_id.in_(story_ids))
    ) or 0
    return DashboardStats(
        total_stories=stats.total_stories,
        total_images=stats.total_images,
        total_videos=stats.total_videos,
        total_scenes=total_scenes,
        generation_seconds=stats.total_generation_seconds,
    )


def user_public(user: User) -> UserPublic:
    """Return a safe user model."""
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


def settings_response(settings: UserSettings | None) -> UserSettingsResponse:
    """Return settings with defaults."""
    if settings is None:
        return UserSettingsResponse()

    return UserSettingsResponse(
        theme=settings.theme if settings.theme in {"dark", "light"} else "light",
        language=settings.language,
        voice_selection=settings.voice_selection,
        image_provider=settings.image_provider,
        background_music_enabled=settings.background_music_enabled,
    )


def build_dashboard(db: Session, user: User) -> DashboardResponse:
    """Return dashboard data for one user."""
    ensure_user_rows(db, user)
    cards = list_history_cards(db, user, page=1, page_size=6).items
    stats = dashboard_stats(db, user.id)
    db.commit()
    return DashboardResponse(
        user=user_public(user),
        stats=stats,
        recent_stories=cards,
        latest_activity=cards[:4],
    )


def list_history_cards(
    db: Session,
    user: User,
    search: str = "",
    sort: str = "newest",
    page: int = 1,
    page_size: int = 12,
) -> PaginatedHistoryResponse:
    """Return paginated user history cards."""
    page = max(1, page)
    page_size = min(50, max(1, page_size))
    query = (
        select(Story)
        .where(Story.user_id == user.id)
        .options(
            selectinload(Story.scenes).selectinload(SceneRecord.images),
            selectinload(Story.videos),
            selectinload(Story.history_items),
        )
    )
    if search:
        needle = f"%{search.lower()}%"
        query = query.where(
            or_(
                func.lower(Story.title).like(needle),
                func.lower(Story.story).like(needle),
            )
        )

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    order_by = Story.created_at.asc() if sort == "oldest" else Story.created_at.desc()
    stories = db.scalars(
        query.order_by(order_by).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return PaginatedHistoryResponse(
        items=[history_card(story) for story in stories],
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, ceil(total / page_size)) if total else 1,
    )


def history_card(story: Story) -> HistoryCard:
    """Build one history card."""
    video = story.videos[-1] if story.videos else None
    image_records = [
        image
        for scene in story.scenes
        for image in scene.images
        if image.status == "success"
    ]
    thumbnail = video.thumbnail_url if video and video.thumbnail_url else None
    if thumbnail is None and image_records:
        thumbnail = image_records[0].image_url or image_records[0].image_path

    history_time = (
        story.history_items[-1].generation_time if story.history_items else story.created_at
    )
    return HistoryCard(
        story_id=story.story_id,
        file_name=story.file_name,
        title=story.title,
        created_at=story.created_at,
        generation_time=history_time,
        status=story.status,
        thumbnail_url=thumbnail,
        images_count=len(image_records),
        video_duration=video.duration if video else None,
        video_url=video.video_url if video else None,
    )


def get_story_for_user(db: Session, user: User, story_id: int) -> Story | None:
    """Return one fully loaded story owned by a user."""
    return db.scalar(
        select(Story)
        .where(Story.user_id == user.id, Story.story_id == story_id)
        .options(
            selectinload(Story.scenes).selectinload(SceneRecord.prompt),
            selectinload(Story.scenes).selectinload(SceneRecord.images),
            selectinload(Story.scenes).selectinload(SceneRecord.audio),
            selectinload(Story.videos),
        )
    )


def story_detail_response(story: Story) -> StoryDetailResponse:
    """Convert a database story into API detail shape."""
    scenes = [
        Scene(scene=scene.scene_number, description=scene.description)
        for scene in story.scenes
    ]
    prompts = [
        Prompt(scene=scene.scene_number, prompt=scene.prompt.prompt_text)
        for scene in story.scenes
        if scene.prompt is not None
    ]
    images = [
        ImageResponse(
            scene=scene.scene_number,
            status=image.status,
            image_path=image.image_path,
            image_url=image.image_url,
            provider=image.provider,
            warning=image.warning,
            error=image.error,
        )
        for scene in story.scenes
        for image in scene.images
    ]
    audio = [
        AudioResponse(
            scene=scene.scene_number,
            status=audio_item.status,
            audio_path=audio_item.audio_path,
            audio_url=audio_item.audio_url,
            duration_seconds=audio_item.duration,
            error=audio_item.error,
        )
        for scene in story.scenes
        for audio_item in scene.audio
    ]
    video = story.videos[-1] if story.videos else None
    return StoryDetailResponse(
        story_id=story.story_id,
        file_name=story.file_name,
        title=story.title,
        story=story.story,
        created_at=story.created_at,
        status=story.status,
        target_duration_seconds=story.target_duration_seconds,
        generation_duration_seconds=story.generation_duration_seconds,
        scenes=scenes,
        prompts=prompts,
        images=images,
        audio=audio,
        video_path=video.video_path if video else None,
        video_url=video.video_url if video else None,
        thumbnail_url=video.thumbnail_url if video else None,
        video_duration_seconds=video.duration if video else None,
    )


def history_detail_from_story(story: Story) -> HistoryDetail:
    """Build a legacy-compatible HistoryDetail from a database story."""
    detail = story_detail_response(story)
    return HistoryDetail(
        story=detail.story,
        target_duration_seconds=detail.target_duration_seconds,
        scenes=detail.scenes,
        prompts=detail.prompts,
        images=detail.images,
        audio=detail.audio,
        video_path=detail.video_path,
        video_url=detail.video_url,
        thumbnail_url=detail.thumbnail_url,
        video_duration_seconds=detail.video_duration_seconds,
        generation_duration_seconds=detail.generation_duration_seconds,
    )


def list_image_library(
    db: Session,
    user: User,
    provider: str | None = None,
) -> list[ImageLibraryItem]:
    """Return all images owned by a user."""
    query = (
        select(ImageRecord, SceneRecord, Story)
        .join(SceneRecord, ImageRecord.scene_id == SceneRecord.scene_id)
        .join(Story, SceneRecord.story_id == Story.story_id)
        .where(Story.user_id == user.id)
        .order_by(ImageRecord.created_at.desc())
    )
    if provider:
        query = query.where(ImageRecord.provider == provider)

    return [
        ImageLibraryItem(
            image_id=image.image_id,
            story_id=story.story_id,
            scene_number=scene.scene_number,
            title=story.title,
            prompt=scene.prompt.prompt_text if scene.prompt else None,
            image_url=image.image_url,
            image_path=image.image_path,
            provider=image.provider,
            status=image.status,
            created_at=image.created_at,
        )
        for image, scene, story in db.execute(query).all()
    ]


def list_video_library(db: Session, user: User) -> list[VideoLibraryItem]:
    """Return all videos owned by a user."""
    query = (
        select(VideoRecord, Story)
        .join(Story, VideoRecord.story_id == Story.story_id)
        .where(Story.user_id == user.id)
        .order_by(VideoRecord.created_at.desc())
    )
    return [
        VideoLibraryItem(
            video_id=video.video_id,
            story_id=story.story_id,
            title=story.title,
            video_url=video.video_url,
            video_path=video.video_path,
            thumbnail_url=video.thumbnail_url,
            duration=video.duration,
            created_at=video.created_at,
        )
        for video, story in db.execute(query).all()
    ]


def delete_story_for_user(db: Session, user: User, story_id: int) -> bool:
    """Delete a story metadata record owned by the user."""
    story = db.scalar(select(Story).where(Story.user_id == user.id, Story.story_id == story_id))
    if story is None:
        return False

    db.delete(story)
    refresh_user_statistics(db, user.id)
    db.commit()
    return True


def delete_image_for_user(db: Session, user: User, image_id: int) -> bool:
    """Delete one image metadata record owned by the user."""
    image = db.scalar(
        select(ImageRecord)
        .join(SceneRecord)
        .join(Story)
        .where(Story.user_id == user.id, ImageRecord.image_id == image_id)
    )
    if image is None:
        return False

    db.delete(image)
    refresh_user_statistics(db, user.id)
    db.commit()
    return True


def delete_video_for_user(db: Session, user: User, video_id: int) -> bool:
    """Delete one video metadata record owned by the user."""
    video = db.scalar(
        select(VideoRecord)
        .join(Story)
        .where(Story.user_id == user.id, VideoRecord.video_id == video_id)
    )
    if video is None:
        return False

    db.delete(video)
    refresh_user_statistics(db, user.id)
    db.commit()
    return True


def profile_response(db: Session, user: User) -> ProfileResponse:
    """Return profile data."""
    ensure_user_rows(db, user)
    stats = dashboard_stats(db, user.id)
    db.commit()
    db.refresh(user)
    return ProfileResponse(
        user=user_public(user),
        stats=stats,
        settings=settings_response(user.settings),
    )


def user_media_dirs(user: User | None, story_key: str) -> dict[str, Path]:
    """Return output directories, optionally partitioned by user/story."""
    if user is None:
        return {
            "images": Path("outputs/images"),
            "audio": Path("outputs/audio"),
            "videos": Path("outputs/videos"),
        }

    user_key = str(user.id)
    return {
        "images": Path("outputs/images") / "users" / user_key / story_key,
        "audio": Path("outputs/audio") / "users" / user_key / story_key,
        "videos": Path("outputs/videos") / "users" / user_key,
    }
