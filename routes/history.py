"""History API routes for saved CineGen AI generations."""

import os

from fastapi import APIRouter, HTTPException, Request, status

from models.story import HistoryDetail, HistoryItem, HistoryStats, ImageResponse
from services.history_service import HistoryService
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
async def list_history() -> list[HistoryItem]:
    """Return valid saved story output files, newest first."""
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
async def get_history_stats() -> HistoryStats:
    """Return aggregate counts from valid saved story output files."""
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
async def get_history_detail(request: Request, filename: str) -> HistoryDetail:
    """Return one saved story output without regenerating content."""
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
    """Attach browser-accessible image URLs to history detail responses."""
    public_base_url = _get_public_base_url(request_base_url)
    images: list[ImageResponse] = []

    for image in detail.images:
        if image.image_path:
            image_path = image.image_path.replace("\\", "/").lstrip("/")
            image_url = f"{public_base_url}/{image_path}"
            logger.info(
                "History image URL generated for scene %s: status=%s path=%s url=%s",
                image.scene,
                image.status,
                image_path,
                image_url,
            )
            images.append(image.model_copy(update={"image_url": image_url}))
        else:
            images.append(image.model_copy(update={"image_url": None}))

    return detail.model_copy(update={"images": images})


def _get_public_base_url(request_base_url: str | None) -> str:
    """Return the public API base URL used for history image links."""
    configured_url = os.getenv("CINEGEN_PUBLIC_BASE_URL")
    if configured_url:
        return configured_url.rstrip("/")

    if request_base_url:
        return request_base_url.rstrip("/")

    return "http://127.0.0.1:8001"
