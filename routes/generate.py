"""Story generation API routes."""

import os
import traceback
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool

from models.story import (
    GenerateImageResponse,
    ImageGenerationRequest,
    ImageResponse,
    ImageSummary,
    Scene,
    StoryRequest,
    StoryResponse,
)
from services.image_generator import ImageGenerator
from services.llm_scene_generator import LLMSceneGenerator
from services.prompt_generator import PromptGenerator
from utils.file_handler import FileHandler, FileSaveError
from utils.logger import get_logger

router = APIRouter(tags=["Story Generation"])
logger = get_logger(__name__)

scene_generator = LLMSceneGenerator()
prompt_generator = PromptGenerator()
IMAGE_TIMEOUT_SECONDS = 300
image_generator = ImageGenerator(generation_timeout_seconds=IMAGE_TIMEOUT_SECONDS)
file_handler = FileHandler()
IMAGE_FAILURE_MESSAGE = "Image generation failed. Story generation completed."
IMAGE_DEFERRED_MESSAGE = "Story and prompts generated. Generate images one scene at a time."


@router.post(
    "/generate-story",
    response_model=StoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate scenes, prompts, images, and save the completed story result",
)
async def generate_story(api_request: Request, request: StoryRequest) -> StoryResponse:
    """Process a story into scenes, prompts, saved images, and JSON output.

    Image generation is synchronous by default. The legacy defer_images flag remains
    supported for existing clients that still use the per-scene image endpoint.
    """
    logger.info(
        "API request received: POST /generate-story text_only=%s defer_images=%s",
        request.text_only,
        request.defer_images,
    )

    story = request.story.strip()
    if not story:
        logger.warning("Empty story submitted")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Story cannot be empty.",
        )

    try:
        scenes = scene_generator.extract_scenes(story)
        logger.info("Scene extraction completed: %s scenes", len(scenes))

        if not scenes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Story must contain at least one valid scene.",
            )

        prompts = prompt_generator.generate_prompts(scenes)
        logger.info("Prompt generation completed: %s prompts", len(prompts))

        defer_images = bool(request.defer_images)

        if request.text_only:
            images = _build_skipped_images(scenes)
            logger.info("Image generation skipped by text-only mode")
        elif defer_images:
            images = _build_deferred_images(scenes)
            logger.info("Image generation deferred for per-scene requests")
        else:
            try:
                logger.info(
                    "Synchronous image generation started: prompts=%s timeout_per_image=%ss",
                    len(prompts),
                    IMAGE_TIMEOUT_SECONDS,
                )
                images = await run_in_threadpool(
                    image_generator.generate_images,
                    prompts,
                )
                logger.info("Image generation completed: %s image records", len(images))
            except Exception as exc:
                error_trace = traceback.format_exc()
                logger.exception(error_trace)
                images = image_generator.build_failed_images(
                    prompts,
                    error_trace or str(exc),
                )

        images = _attach_image_urls(
            images,
            request_base_url=str(api_request.base_url),
        )

        image_summary = _build_image_summary(
            images=images,
            requested=not request.text_only,
        )
        response_status = _build_response_status(image_summary)
        message = _build_response_message(response_status, image_summary)

        logger.info("Saving completed story result")
        file_name = file_handler.save_story_result(
            story=story,
            scenes=scenes,
            prompts=prompts,
            images=images,
            image_summary=image_summary,
            status=response_status,
            message=message,
        )
        logger.info("File saved successfully: %s", file_name)

        return StoryResponse(
            success=True,
            status=response_status,
            message=message,
            file_name=file_name,
            scenes=scenes,
            prompts=prompts,
            images=images,
            image_summary=image_summary,
        )
    except HTTPException:
        raise
    except FileSaveError as exc:
        logger.exception("File save error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to save story output.",
        ) from exc
    except Exception as exc:
        logger.exception("Internal server error while processing story")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while processing the story.",
        ) from exc


@router.post(
    "/generate-image",
    response_model=GenerateImageResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate one scene image from a prompt",
)
async def generate_image(
    api_request: Request,
    request: ImageGenerationRequest,
) -> GenerateImageResponse:
    """Generate one scene image and optionally update a saved story file."""
    logger.info(
        "API request received: POST /generate-image scene=%s file_name=%s",
        request.scene,
        request.file_name,
    )

    prompt = request.prompt.strip()
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Prompt cannot be empty.",
        )

    image = await run_in_threadpool(
        image_generator.generate_image_with_fallback,
        prompt,
        request.scene,
    )
    image = _attach_image_urls(
        [image],
        request_base_url=str(api_request.base_url),
    )[0]

    if request.file_name:
        try:
            file_handler.update_story_image(request.file_name, image)
            logger.info(
                "Saved story image status updated: file=%s scene=%s status=%s",
                request.file_name,
                image.scene,
                image.status,
            )
        except FileSaveError as exc:
            logger.exception(
                "Unable to update saved story image status: file=%s scene=%s",
                request.file_name,
                image.scene,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to update saved story image status.",
            ) from exc

    return GenerateImageResponse(
        success=image.status == "success",
        scene=image.scene,
        status=image.status,
        image_path=image.image_path,
        image_url=image.image_url,
        error=image.error,
    )


def _build_skipped_images(scenes: list[Scene]) -> list[ImageResponse]:
    """Return one skipped image record per scene for text-only responses."""
    return [
        ImageResponse(
            scene=scene.scene,
            status="skipped",
            image_path=None,
            image_url=None,
            error="Image generation skipped by text-only mode.",
        )
        for scene in scenes
    ]


def _build_deferred_images(scenes: list[Scene]) -> list[ImageResponse]:
    """Return one deferred image record per scene for per-scene generation."""
    return [
        ImageResponse(
            scene=scene.scene,
            status="skipped",
            image_path=None,
            image_url=None,
            error="Image generation deferred. Use /generate-image for this scene.",
        )
        for scene in scenes
    ]


def _attach_image_urls(
    images: list[ImageResponse],
    request_base_url: str | None,
) -> list[ImageResponse]:
    """Attach browser-accessible URLs to saved scene image records."""
    public_base_url = _get_public_base_url(request_base_url)
    enriched_images: list[ImageResponse] = []

    for image in images:
        if image.image_path:
            image_path = image.image_path.replace("\\", "/").lstrip("/")
            image_url = f"{public_base_url}/{image_path}"
            logger.info(
                "Image URL generated for scene %s: status=%s path=%s url=%s",
                image.scene,
                image.status,
                image_path,
                image_url,
            )
            enriched_images.append(image.model_copy(update={"image_url": image_url}))
        else:
            enriched_images.append(image.model_copy(update={"image_url": None}))

    return enriched_images


def _get_public_base_url(request_base_url: str | None) -> str:
    """Return the public API base URL used for generated image links."""
    configured_url = os.getenv("CINEGEN_PUBLIC_BASE_URL")
    if configured_url:
        return configured_url.rstrip("/")

    if request_base_url:
        return request_base_url.rstrip("/")

    return "http://127.0.0.1:8001"


def _build_image_summary(images: list[ImageResponse], requested: bool) -> ImageSummary:
    """Summarize scene-level image results."""
    return ImageSummary(
        requested=requested,
        total=len(images),
        succeeded=sum(1 for image in images if image.status == "success"),
        failed=sum(1 for image in images if image.status == "failed"),
        skipped=sum(1 for image in images if image.status == "skipped"),
    )


def _build_response_status(
    image_summary: ImageSummary,
) -> Literal["completed", "partial", "text_only"]:
    """Build the top-level response status from image generation results."""
    if not image_summary.requested:
        return "text_only"

    if image_summary.failed:
        return "partial"

    return "completed"


def _build_response_message(
    response_status: Literal["completed", "partial", "text_only"],
    image_summary: ImageSummary,
) -> str:
    """Build a concise user-facing status message."""
    if response_status == "text_only":
        return "Story processed in text-only mode; image generation skipped."

    if response_status == "partial":
        return IMAGE_FAILURE_MESSAGE

    if image_summary.requested and image_summary.skipped:
        return IMAGE_DEFERRED_MESSAGE

    return "Story processed successfully."
