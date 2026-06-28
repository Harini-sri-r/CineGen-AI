"""Pydantic models for CineGen AI story processing."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MIN_STORY_LENGTH = 3
DEFAULT_VIDEO_DURATION_SECONDS = 30
MIN_VIDEO_DURATION_SECONDS = 10
MAX_VIDEO_DURATION_SECONDS = 120


class StoryRequest(BaseModel):
    """Request body for story processing."""

    story: str = Field(
        ...,
        min_length=MIN_STORY_LENGTH,
        max_length=50_000,
        description="Story text or short story idea to expand into scenes.",
        examples=[
            (
                "A girl enters a magical forest. She finds a glowing deer. "
                "The deer guides her to a waterfall."
            )
        ],
    )
    text_only: bool = Field(
        default=False,
        description="Skip image generation and return only scenes, prompts, and JSON output.",
    )
    defer_images: bool = Field(
        default=False,
        description=(
            "Return scenes and prompts immediately and generate images later with "
            "the per-scene image API."
        ),
    )
    target_duration_seconds: int = Field(
        default=DEFAULT_VIDEO_DURATION_SECONDS,
        ge=MIN_VIDEO_DURATION_SECONDS,
        le=MAX_VIDEO_DURATION_SECONDS,
        description="Target MP4 video duration in seconds.",
    )

    @field_validator("story")
    @classmethod
    def normalize_story(cls, value: str) -> str:
        """Trim and validate submitted story text."""
        story = value.strip()
        if not story:
            raise ValueError("Story cannot be empty.")

        if len(story) < MIN_STORY_LENGTH:
            raise ValueError(
                f"Story must be at least {MIN_STORY_LENGTH} characters long."
            )

        return story


class Scene(BaseModel):
    """A numbered scene extracted from the story."""

    scene: int = Field(..., ge=1, description="One-based scene number.")
    description: str = Field(..., min_length=1, description="Scene description.")


class Prompt(BaseModel):
    """A cinematic prompt generated for an extracted scene."""

    scene: int = Field(..., ge=1, description="One-based scene number.")
    prompt: str = Field(..., min_length=1, description="Generated cinematic prompt.")


class ImageResponse(BaseModel):
    """Generated image metadata or failure details for a scene."""

    scene: int = Field(..., ge=1, description="One-based scene number.")
    status: Literal["success", "failed", "skipped"] = Field(
        ...,
        description="Image generation result for this scene.",
    )
    image_path: str | None = Field(
        default=None,
        min_length=1,
        description="Relative path to the generated image file.",
        examples=["outputs/images/scene_1.png"],
    )
    image_url: str | None = Field(
        default=None,
        min_length=1,
        description="Browser-accessible URL for the generated image file.",
        examples=["http://127.0.0.1:8001/outputs/images/scene_1.png"],
    )
    provider: str | None = Field(
        default=None,
        description=(
            "Image provider that produced this file, such as huggingface, fal, "
            "pollinations, storyboard, stable-diffusion, or placeholder."
        ),
    )
    warning: str | None = Field(
        default=None,
        description="Non-fatal image generation warning, such as fallback usage.",
    )
    error: str | None = Field(
        default=None,
        description="Scene-level image generation error, if generation failed.",
    )


class ImageSummary(BaseModel):
    """Aggregate image generation status for a story request."""

    requested: bool = Field(..., description="Whether image generation was requested.")
    total: int = Field(..., ge=0, description="Total scene image records returned.")
    succeeded: int = Field(..., ge=0, description="Number of generated images.")
    failed: int = Field(..., ge=0, description="Number of failed image generations.")
    skipped: int = Field(..., ge=0, description="Number of skipped image generations.")


class AudioResponse(BaseModel):
    """Generated narration metadata or failure details for a scene."""

    scene: int = Field(..., ge=1, description="One-based scene number.")
    status: Literal["success", "failed", "skipped"] = Field(
        ...,
        description="Narration generation result for this scene.",
    )
    audio_path: str | None = Field(
        default=None,
        min_length=1,
        description="Relative path to the generated narration file.",
        examples=["outputs/audio/scene_1.mp3"],
    )
    audio_url: str | None = Field(
        default=None,
        min_length=1,
        description="Browser-accessible URL for the generated narration file.",
    )
    duration_seconds: float | None = Field(
        default=None,
        ge=0,
        description="Measured narration duration in seconds.",
    )
    error: str | None = Field(
        default=None,
        description="Scene-level narration error, if generation failed.",
    )


class ImageGenerationRequest(BaseModel):
    """Request body for generating a single scene image."""

    scene: int = Field(..., ge=1, description="One-based scene number.")
    prompt: str = Field(..., min_length=1, description="Scene prompt to render.")
    file_name: str | None = Field(
        default=None,
        description="Optional saved story JSON filename to update with image status.",
    )


class GenerateImageResponse(BaseModel):
    """Response body for one per-scene image generation request."""

    success: bool
    scene: int = Field(..., ge=1)
    status: Literal["success", "failed", "skipped"]
    image_path: str | None = None
    image_url: str | None = None
    provider: str | None = None
    warning: str | None = None
    error: str | None = None


class VideoGenerationRequest(BaseModel):
    """Request body for generating a complete story video."""

    story: str = Field(
        ...,
        min_length=MIN_STORY_LENGTH,
        max_length=50_000,
        description="Story text or short story idea to transform into a narrated MP4 video.",
    )
    file_name: str | None = Field(
        default=None,
        description="Optional saved story JSON filename whose images can be reused.",
    )
    target_duration_seconds: int = Field(
        default=DEFAULT_VIDEO_DURATION_SECONDS,
        ge=MIN_VIDEO_DURATION_SECONDS,
        le=MAX_VIDEO_DURATION_SECONDS,
        description="Target MP4 video duration in seconds.",
    )

    @field_validator("story")
    @classmethod
    def normalize_story(cls, value: str) -> str:
        """Trim and validate submitted story text."""
        return StoryRequest.normalize_story(value)


class VideoGenerationResponse(BaseModel):
    """Response body for a complete story-to-video generation request."""

    success: bool
    status: Literal["completed", "partial", "failed"]
    message: str
    file_name: str | None = None
    story: str
    scenes: list[Scene]
    prompts: list[Prompt]
    images: list[ImageResponse]
    image_summary: ImageSummary
    audio: list[AudioResponse] = Field(default_factory=list)
    video_path: str | None = None
    video_url: str | None = None
    thumbnail_url: str | None = None
    duration: str
    duration_seconds: float = Field(..., ge=0)
    target_duration_seconds: int = Field(..., ge=MIN_VIDEO_DURATION_SECONDS)
    scene_count: int = Field(..., ge=0)
    generation_duration_seconds: float = Field(..., ge=0)
    error: str | None = None


class StoryResponse(BaseModel):
    """Successful story processing response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "status": "partial",
                "message": "Story processed with 1 image failure.",
                "file_name": "story_20260623_120000.json",
                "scenes": [
                    {"scene": 1, "description": "A girl enters a magical forest"},
                    {"scene": 2, "description": "She finds a glowing deer"},
                    {"scene": 3, "description": "The deer guides her to a waterfall"},
                ],
                "prompts": [
                    {
                        "scene": 1,
                        "prompt": (
                            "cinematic fantasy forest, magical lighting, "
                            "a girl enters a magical forest, cinematic composition, "
                            "dramatic lighting, ultra realistic, 4k movie scene"
                        ),
                    }
                ],
                "images": [
                    {
                        "scene": 1,
                        "status": "success",
                        "image_path": "outputs/images/scene_1.png",
                        "image_url": (
                            "http://127.0.0.1:8001/outputs/images/scene_1.png"
                        ),
                        "error": None,
                    },
                    {
                        "scene": 2,
                        "status": "failed",
                        "image_path": "outputs/images/scene_2.png",
                        "image_url": (
                            "http://127.0.0.1:8001/outputs/images/scene_2.png"
                        ),
                        "error": "Image generation failed for scene 2.",
                    },
                    {
                        "scene": 3,
                        "status": "success",
                        "image_path": "outputs/images/scene_3.png",
                        "image_url": (
                            "http://127.0.0.1:8001/outputs/images/scene_3.png"
                        ),
                        "error": None,
                    },
                ],
                "image_summary": {
                    "requested": True,
                    "total": 3,
                    "succeeded": 2,
                    "failed": 1,
                    "skipped": 0,
                },
            }
        }
    )

    success: bool
    status: Literal["completed", "partial", "text_only"]
    message: str
    file_name: str
    story: str
    target_duration_seconds: int = Field(
        default=DEFAULT_VIDEO_DURATION_SECONDS,
        ge=MIN_VIDEO_DURATION_SECONDS,
        le=MAX_VIDEO_DURATION_SECONDS,
    )
    scenes: list[Scene]
    prompts: list[Prompt]
    images: list[ImageResponse]
    image_summary: ImageSummary
    audio: list[AudioResponse] = Field(default_factory=list)
    video_path: str | None = None
    video_url: str | None = None
    thumbnail_url: str | None = None
    video_duration_seconds: float | None = None
    generation_duration_seconds: float | None = None


class HistoryItem(BaseModel):
    """Summary metadata for one saved story output."""

    file: str = Field(..., min_length=1, description="Saved output JSON filename.")
    created_at: str = Field(
        ...,
        description="Story creation timestamp formatted as YYYY-MM-DD HH:MM:SS.",
        examples=["2026-06-24 17:32:28"],
    )


class HistoryDetail(BaseModel):
    """Saved story output returned from the history endpoint."""

    story: str = Field(..., description="Original submitted story.")
    target_duration_seconds: int | None = None
    scenes: list[Scene]
    prompts: list[Prompt]
    images: list[ImageResponse]
    audio: list[AudioResponse] = Field(default_factory=list)
    video_path: str | None = None
    video_url: str | None = None
    thumbnail_url: str | None = None
    video_duration_seconds: float | None = None
    generation_duration_seconds: float | None = None


class HistoryStats(BaseModel):
    """Aggregate statistics calculated from saved story outputs."""

    total_stories: int = Field(..., ge=0)
    total_scenes: int = Field(..., ge=0)
    total_images: int = Field(..., ge=0)
