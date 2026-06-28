"""History API routes for saved CineGen AI generations."""

import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from auth_dependencies import get_optional_current_user
from database import get_db
from db_models import Scene as SceneRecord
from db_models import Story, User
from models.story import AudioResponse, HistoryDetail, HistoryItem, HistoryStats, ImageResponse
from services.history_service import HistoryService
from services.saas_service import dashboard_stats, history_detail_from_story
from utils.logger import get_logger

router = APIRouter(tags=["History"])
logger = get_logger(__name__)

history_service = HistoryService()


@router.get(
    "/history",
    response_model=list[HistoryItem],
    status_code=status.HTTP_200_OK,
    summary="List saved story generations",
)
async def list_history(
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
) -> list[HistoryItem]:
    """Return valid saved story output files, newest first."""
    if current_user is not None:
        stories = db.scalars(
            select(Story)
            .where(Story.user_id == current_user.id)
            .order_by(Story.created_at.desc())
        ).all()
        return [
            HistoryItem(
                file=story.file_name or f"story_{story.story_id}.json",
                created_at=story.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            )
            for story in stories
        ]

    try:
        return history_service.list_history()
    except Exception as exc:
        logger.exception("Unable to list history")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to load generation history.",
        ) from exc


@router.get(
    "/history/stats",
    response_model=HistoryStats,
    status_code=status.HTTP_200_OK,
    summary="Calculate generation history statistics",
)
async def get_history_stats(
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
) -> HistoryStats:
    """Return aggregate counts from valid saved story output files."""
    if current_user is not None:
        stats = dashboard_stats(db, current_user.id)
        return HistoryStats(
            total_stories=stats.total_stories,
            total_scenes=stats.total_scenes,
            total_images=stats.total_images,
        )

    try:
        return history_service.get_stats()
    except Exception as exc:
        logger.exception("Unable to calculate history stats")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to calculate generation history statistics.",
        ) from exc


@router.get(
    "/history/{filename}",
    response_model=HistoryDetail,
    status_code=status.HTTP_200_OK,
    summary="Get a saved story generation",
)
async def get_history_detail(
    request: Request,
    filename: str,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
) -> HistoryDetail:
    """Return one saved story output without regenerating content."""
    if current_user is not None:
        story = db.scalar(
            select(Story)
            .where(Story.user_id == current_user.id, Story.file_name == filename)
            .options(
                selectinload(Story.scenes).selectinload(SceneRecord.prompt),
                selectinload(Story.scenes).selectinload(SceneRecord.images),
                selectinload(Story.scenes).selectinload(SceneRecord.audio),
                selectinload(Story.videos),
            )
        )
        if story is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="History file not found.",
            )

        return _attach_history_image_urls(
            history_detail_from_story(story),
            request_base_url=str(request.base_url),
        )

    try:
        detail = history_service.get_history_detail(filename)
    except Exception as exc:
        logger.exception("Unable to load history file: %s", filename)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to load generation history item.",
        ) from exc

    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="History file not found.",
        )

    return _attach_history_image_urls(
        detail,
        request_base_url=str(request.base_url),
    )


def _attach_history_image_urls(
    detail: HistoryDetail,
    request_base_url: str | None,
) -> HistoryDetail:
    """Attach browser-accessible media URLs to history detail responses."""
    public_base_url = _get_public_base_url(request_base_url)
    images: list[ImageResponse] = []
    audio: list[AudioResponse] = []

    for image in detail.images:
        if image.image_path:
            image_url = _build_media_url(
                image.image_path,
                public_base_url=public_base_url,
                cache_bust=True,
            )
            logger.info(
                "History image URL generated for scene %s: status=%s path=%s url=%s",
                image.scene,
                image.status,
                image.image_path,
                image_url,
            )
            images.append(image.model_copy(update={"image_url": image_url}))
        else:
            images.append(image.model_copy(update={"image_url": None}))

    for audio_item in detail.audio:
        if audio_item.audio_path:
            audio.append(
                audio_item.model_copy(
                    update={
                        "audio_url": _build_media_url(
                            audio_item.audio_path,
                            public_base_url=public_base_url,
                        )
                    }
                )
            )
        else:
            audio.append(audio_item.model_copy(update={"audio_url": None}))

    video_url = detail.video_url
    if detail.video_path:
        video_url = _build_media_url(detail.video_path, public_base_url=public_base_url)
    elif video_url and not video_url.startswith(("http://", "https://")):
        video_url = _build_media_url(video_url, public_base_url=public_base_url)

    return detail.model_copy(
        update={
            "images": images,
            "audio": audio,
            "video_url": video_url,
        }
    )


def _build_media_url(
    media_path: str,
    public_base_url: str,
    cache_bust: bool = False,
) -> str:
    """Build a browser URL for a saved output path."""
    if media_path.startswith(("http://", "https://")):
        return media_path

    normalized_path = media_path.replace("\\", "/").lstrip("/")
    cache_buster = _build_cache_buster(normalized_path) if cache_bust else ""
    return f"{public_base_url}/{normalized_path}{cache_buster}"


def _build_cache_buster(media_path: str) -> str:
    """Return a cache-busting query for local generated media."""
    normalized_path = Path(media_path.replace("\\", "/"))
    if normalized_path.is_absolute() or ".." in normalized_path.parts:
        return ""

    try:
        return f"?v={int(normalized_path.stat().st_mtime)}"
    except OSError:
        return ""


def _get_public_base_url(request_base_url: str | None) -> str:
    """Return the public API base URL used for history image links."""
    configured_url = os.getenv("CINEGEN_PUBLIC_BASE_URL")
    if configured_url:
        return configured_url.rstrip("/")

    if request_base_url:
        return request_base_url.rstrip("/")

    return "http://127.0.0.1:8001"
