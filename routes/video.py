"""Story-to-video API routes."""

from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
from time import perf_counter
import traceback

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError

from models.story import (
    AudioResponse,
    ImageResponse,
    ImageSummary,
    Prompt,
    Scene,
    VideoGenerationRequest,
    VideoGenerationResponse,
)
from services.image_generator import ImageGenerator
from services.llm_scene_generator import LLMSceneGenerator
from services.prompt_generator import PromptGenerator
from services.scene_generator import SceneGenerator
from services.story_composer import StoryComposer
from services.tts_generator import TTSGenerator
from services.video_generator import VideoGenerationError, VideoGenerator
from utils.file_handler import FileHandler, FileSaveError
from utils.logger import get_logger

router = APIRouter(tags=["Video Generation"])
logger = get_logger(__name__)

scene_generator = LLMSceneGenerator()
fast_scene_generator = SceneGenerator()
prompt_generator = PromptGenerator()
story_composer = StoryComposer()
image_generator = ImageGenerator(generation_timeout_seconds=300)
tts_generator = TTSGenerator()
video_generator = VideoGenerator()
file_handler = FileHandler()


@router.post(
    "/generate-video",
    response_model=VideoGenerationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate a narrated MP4 video from a story",
)
async def generate_video(
    api_request: Request,
    request: VideoGenerationRequest,
) -> VideoGenerationResponse:
    """Create a complete story-to-video generation."""
    user_story = request.story.strip()
    story = story_composer.compose(
        user_story,
        target_duration_seconds=request.target_duration_seconds,
    )
    expanded_from_idea = story != " ".join(user_story.split()).strip()
    started_at = perf_counter()
    saved_payload = _read_reusable_payload(request.file_name, story)

    try:
        scenes, prompts, images = await _prepare_story_media(
            story,
            saved_payload,
            expanded_from_idea=expanded_from_idea,
        )
        images = _attach_image_urls(images, str(api_request.base_url))
        image_summary = _build_image_summary(images)
        if not _has_successful_images(images):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Generate at least one successful scene image before creating a video.",
            )

        audio = await _generate_audio_with_fallback(scenes)

        output_file_name = request.file_name or _build_story_file_name()
        video_output_name = output_file_name.replace(".json", ".mp4")
        video_result = await run_in_threadpool(
            video_generator.create_video,
            scenes,
            images,
            audio,
            video_output_name,
            request.target_duration_seconds,
        )
    except VideoGenerationError as exc:
        detail = str(exc) or traceback.format_exc()
        logger.exception("Video generation failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        detail = traceback.format_exc()
        logger.exception("Video pipeline failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
        ) from exc

    generation_duration_seconds = perf_counter() - started_at
    video_path = video_result.video_path
    video_url = _build_public_url(video_path, str(api_request.base_url))
    audio = _attach_audio_urls(audio, str(api_request.base_url))
    thumbnail_url = _first_successful_image_url(images)
    response_status = "partial" if image_summary.failed else "completed"
    message = "Story video generated successfully."

    try:
        if request.file_name and saved_payload is not None:
            file_handler.update_story_video(
                request.file_name,
                audio=audio,
                video_path=video_path,
                thumbnail_url=thumbnail_url,
                video_duration_seconds=video_result.duration_seconds,
                target_duration_seconds=request.target_duration_seconds,
                generation_duration_seconds=generation_duration_seconds,
                status=response_status,
                message=message,
            )
            file_name = request.file_name
        else:
            file_name = file_handler.save_story_result(
                story=story,
                scenes=scenes,
                prompts=prompts,
                images=images,
                image_summary=image_summary,
                audio=audio,
                video_path=video_path,
                video_url=video_path,
                thumbnail_url=thumbnail_url,
                video_duration_seconds=video_result.duration_seconds,
                target_duration_seconds=request.target_duration_seconds,
                generation_duration_seconds=generation_duration_seconds,
                status=response_status,
                message=message,
                file_name=output_file_name,
            )
    except FileSaveError as exc:
        logger.exception("Unable to save video generation metadata")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Video was created, but metadata could not be saved.",
        ) from exc

    return VideoGenerationResponse(
        success=True,
        status=response_status,
        message=message,
        file_name=file_name,
        story=story,
        scenes=scenes,
        prompts=prompts,
        images=images,
        image_summary=image_summary,
        audio=audio,
        video_path=video_path,
        video_url=video_url,
        thumbnail_url=thumbnail_url,
        duration=_format_duration(video_result.duration_seconds),
        duration_seconds=video_result.duration_seconds,
        target_duration_seconds=request.target_duration_seconds,
        scene_count=len(scenes),
        generation_duration_seconds=generation_duration_seconds,
        error=None,
    )


async def _prepare_story_media(
    story: str,
    saved_payload: dict | None,
    expanded_from_idea: bool = False,
) -> tuple[list[Scene], list[Prompt], list[ImageResponse]]:
    """Extract or reuse scenes, prompts, and images for the video pipeline."""
    if saved_payload is not None:
        try:
            scenes = [
                Scene.model_validate(item)
                for item in saved_payload.get("scenes", [])
                if isinstance(item, dict)
            ]
            prompts = [
                Prompt.model_validate(item)
                for item in saved_payload.get("prompts", [])
                if isinstance(item, dict)
            ]
            images = [
                ImageResponse.model_validate(item)
                for item in saved_payload.get("images", [])
                if isinstance(item, dict)
            ]
        except ValidationError:
            scenes, prompts, images = [], [], []

        if scenes and prompts and _can_reuse_images(images, prompts):
            logger.info("Reusing saved images for video generation")
            return scenes, prompts, images

    if expanded_from_idea:
        scenes = await run_in_threadpool(fast_scene_generator.extract_scenes, story)
    else:
        scenes = await run_in_threadpool(scene_generator.extract_scenes, story)
    if not scenes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Story must contain at least one valid scene.",
        )

    prompts = await run_in_threadpool(prompt_generator.generate_prompts, scenes)
    images = await run_in_threadpool(image_generator.generate_images, prompts)
    return scenes, prompts, images


async def _generate_audio_with_fallback(scenes: list[Scene]) -> list[AudioResponse]:
    """Generate narration while keeping the video pipeline alive on failure."""
    try:
        return await run_in_threadpool(tts_generator.generate_narrations, scenes)
    except Exception as exc:
        error_trace = traceback.format_exc()
        logger.exception("Narration batch failed")
        logger.exception(error_trace)
        return [
            AudioResponse(
                scene=scene.scene,
                status="failed",
                audio_path=None,
                audio_url=None,
                duration_seconds=None,
                error=str(exc) or error_trace,
            )
            for scene in scenes
        ]


def _read_reusable_payload(file_name: str | None, story: str) -> dict | None:
    """Read a saved story payload when it belongs to the submitted story."""
    if not file_name:
        return None

    try:
        payload = file_handler.read_story_result(file_name)
    except FileSaveError:
        return None

    if str(payload.get("story", "")).strip() != story.strip():
        logger.info("Saved story did not match submitted video story; regenerating media")
        return None

    return payload


def _can_reuse_images(images: list[ImageResponse], prompts: list[Prompt]) -> bool:
    """Return true when saved image records cover all prompted scenes."""
    images_by_scene = {image.scene: image for image in images}
    for prompt in prompts:
        image = images_by_scene.get(prompt.scene)
        if not image or image.status != "success" or not image.image_path:
            return False

        resolved_path = _resolve_output_path(image.image_path)
        if resolved_path is None or not resolved_path.exists():
            return False

    return True


def _has_successful_images(images: list[ImageResponse]) -> bool:
    """Return true when at least one real generated scene image is available."""
    return any(image.status == "success" and image.image_path for image in images)


def _attach_image_urls(
    images: list[ImageResponse],
    request_base_url: str | None,
) -> list[ImageResponse]:
    """Attach browser-accessible image URLs to image records."""
    return [
        image.model_copy(
            update={
                "image_url": _build_public_url(
                    image.image_path,
                    request_base_url,
                    cache_bust=True,
                )
                if image.image_path
                else None
            }
        )
        for image in images
    ]


def _attach_audio_urls(
    audio: list[AudioResponse],
    request_base_url: str | None,
) -> list[AudioResponse]:
    """Attach browser-accessible audio URLs to narration records."""
    return [
        audio_item.model_copy(
            update={
                "audio_url": _build_public_url(audio_item.audio_path, request_base_url)
                if audio_item.audio_path
                else None
            }
        )
        for audio_item in audio
    ]


def _build_public_url(
    media_path: str | None,
    request_base_url: str | None,
    cache_bust: bool = False,
) -> str | None:
    """Build a public URL for saved output media."""
    if not media_path:
        return None

    if media_path.startswith(("http://", "https://")):
        return media_path

    public_base_url = _get_public_base_url(request_base_url)
    normalized_path = media_path.replace("\\", "/").lstrip("/")
    cache_buster = _build_cache_buster(normalized_path) if cache_bust else ""
    return f"{public_base_url}/{normalized_path}{cache_buster}"


def _get_public_base_url(request_base_url: str | None) -> str:
    """Return the public API base URL used for generated media links."""
    configured_url = os.getenv("CINEGEN_PUBLIC_BASE_URL")
    if configured_url:
        return configured_url.rstrip("/")

    if request_base_url:
        return request_base_url.rstrip("/")

    return "http://127.0.0.1:8001"


def _build_cache_buster(media_path: str) -> str:
    """Return a cache-busting query for local generated media."""
    normalized_path = Path(media_path.replace("\\", "/"))
    if normalized_path.is_absolute() or ".." in normalized_path.parts:
        return ""

    try:
        return f"?v={int(normalized_path.stat().st_mtime)}"
    except OSError:
        return ""


def _resolve_output_path(media_path: str) -> Path | None:
    """Resolve a saved output media path."""
    normalized_path = Path(media_path.replace("\\", "/"))
    if normalized_path.is_absolute() or ".." in normalized_path.parts:
        return None

    path_parts = normalized_path.parts
    if path_parts and path_parts[0] == "outputs":
        return Path("outputs").joinpath(*path_parts[1:])

    return Path("outputs") / normalized_path


def _build_image_summary(images: list[ImageResponse]) -> ImageSummary:
    """Summarize scene-level image results."""
    return ImageSummary(
        requested=True,
        total=len(images),
        succeeded=sum(1 for image in images if image.status == "success"),
        failed=sum(1 for image in images if image.status == "failed"),
        skipped=sum(1 for image in images if image.status == "skipped"),
    )


def _first_successful_image_url(images: list[ImageResponse]) -> str | None:
    """Return the first successful image URL for use as a video poster."""
    for image in images:
        if image.status == "success" and image.image_url:
            return image.image_url

    for image in images:
        if image.image_url:
            return image.image_url

    return None


def _format_duration(duration_seconds: float) -> str:
    """Format video duration for the API response."""
    rounded_seconds = max(0, int(round(duration_seconds)))
    return f"{rounded_seconds} seconds"


def _build_story_file_name() -> str:
    """Build a story JSON name for standalone video generation."""
    return f"story_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
