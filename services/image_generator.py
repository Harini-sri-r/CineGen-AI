"""Image generation service for CineGen AI."""

from __future__ import annotations

import base64
from contextlib import nullcontext
from io import BytesIO
import json
import os
from pathlib import Path
import re
from threading import Lock
from time import perf_counter
import traceback
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import unquote_to_bytes
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from models.story import ImageResponse, Prompt
from utils.logger import get_logger

logger = get_logger(__name__)


class ImageGenerationError(RuntimeError):
    """Base error raised by the image generation service."""


class ModelLoadError(ImageGenerationError):
    """Raised when a configured image provider dependency cannot be loaded."""


class InvalidPromptError(ImageGenerationError):
    """Raised when a prompt cannot be used for image generation."""


class ImageSaveError(ImageGenerationError):
    """Raised when a generated image cannot be written to disk."""


class GenerationTimeoutError(ImageGenerationError):
    """Raised when scene image generation exceeds the configured timeout."""


class ImageGenerator:
    """Generate and persist scene images.

    The default provider is Pollinations, which runs remotely and saves the
    returned image to the same local output path used by the frontend. Hugging
    Face, fal.ai, and legacy local Stable Diffusion paths remain available as
    options.
    """

    def __init__(
        self,
        image_provider: str | None = None,
        model_id: str | None = None,
        hf_model_id: str | None = None,
        fal_model_id: str | None = None,
        output_dir: str | Path = "outputs/images",
        image_height: int | None = None,
        image_width: int | None = None,
        num_inference_steps: int | None = None,
        guidance_scale: float | None = None,
        low_memory_mode: bool | None = None,
        generation_timeout_seconds: float | None = None,
    ) -> None:
        self.provider = self._normalize_provider(
            image_provider or os.getenv("CINEGEN_IMAGE_PROVIDER", "pollinations")
        )
        self.model_id = model_id or os.getenv(
            "CINEGEN_SD_MODEL_ID",
            "runwayml/stable-diffusion-v1-5",
        )
        self.hf_model_id = hf_model_id or os.getenv(
            "CINEGEN_HF_MODEL_ID",
            "black-forest-labs/FLUX.1-schnell",
        )
        self.hf_provider = os.getenv("CINEGEN_HF_PROVIDER", "hf-inference")
        self.hf_negative_prompt = os.getenv("CINEGEN_HF_NEGATIVE_PROMPT")
        self.hf_timeout_seconds = self._env_float(
            "CINEGEN_HF_TIMEOUT_SECONDS",
            180.0,
        )
        self.fallback_providers = self._parse_provider_list(
            os.getenv("CINEGEN_IMAGE_FALLBACK_PROVIDERS", "fal,pollinations,storyboard")
        )
        self.fal_model_id = fal_model_id or os.getenv(
            "CINEGEN_FAL_MODEL_ID",
            "fal-ai/flux/schnell",
        )
        self.output_dir = Path(output_dir)
        self.image_height = image_height or self._env_int("CINEGEN_IMAGE_HEIGHT", 256)
        self.image_width = image_width or self._env_int("CINEGEN_IMAGE_WIDTH", 256)
        self.num_inference_steps = num_inference_steps or self._env_int(
            "CINEGEN_INFERENCE_STEPS",
            10,
        )
        self.guidance_scale = guidance_scale or self._env_float(
            "CINEGEN_GUIDANCE_SCALE",
            7.0,
        )
        self.generation_timeout_seconds = (
            generation_timeout_seconds
            if generation_timeout_seconds is not None
            else self._env_float("CINEGEN_IMAGE_TIMEOUT_SECONDS", 90.0)
        )
        self.low_memory_mode = (
            low_memory_mode
            if low_memory_mode is not None
            else self._env_bool("CINEGEN_LOW_MEMORY_MODE", True)
        )
        self.fal_image_size = os.getenv("CINEGEN_FAL_IMAGE_SIZE", "landscape_16_9")
        self.fal_num_inference_steps = self._env_int(
            "CINEGEN_FAL_INFERENCE_STEPS",
            4,
        )
        self.fal_guidance_scale = self._env_float("CINEGEN_FAL_GUIDANCE_SCALE", 3.5)
        self.fal_output_format = os.getenv("CINEGEN_FAL_OUTPUT_FORMAT", "png")
        self.fal_acceleration = os.getenv("CINEGEN_FAL_ACCELERATION", "regular")
        self.fal_sync_mode = self._env_bool("CINEGEN_FAL_SYNC_MODE", True)
        self.fal_enable_safety_checker = self._env_bool(
            "CINEGEN_FAL_ENABLE_SAFETY_CHECKER",
            True,
        )
        self.fal_download_timeout_seconds = self._env_float(
            "CINEGEN_FAL_DOWNLOAD_TIMEOUT_SECONDS",
            60.0,
        )
        self.pollinations_base_url = os.getenv(
            "CINEGEN_POLLINATIONS_BASE_URL",
            "https://gen.pollinations.ai",
        ).rstrip("/")
        self.pollinations_model_id = os.getenv(
            "CINEGEN_POLLINATIONS_MODEL_ID",
            "zimage",
        )
        self.pollinations_image_size = os.getenv(
            "CINEGEN_POLLINATIONS_IMAGE_SIZE",
            "1024x1024",
        )
        self.pollinations_quality = os.getenv(
            "CINEGEN_POLLINATIONS_QUALITY",
            "medium",
        )
        self.pollinations_safe = os.getenv("CINEGEN_POLLINATIONS_SAFE", "true")
        self.pollinations_timeout_seconds = self._env_float(
            "CINEGEN_POLLINATIONS_TIMEOUT_SECONDS",
            180.0,
        )

        self.pipeline: Any | None = None
        self.device = "cpu"
        self._torch: Any | None = None
        self._batch_lock = Lock()
        self._load_lock = Lock()
        self._generation_lock = Lock()

        self.output_dir.mkdir(parents=True, exist_ok=True)

    def load_model(self) -> Any:
        """Load and cache the Stable Diffusion pipeline."""
        if self.provider in {"fal", "huggingface", "pollinations"}:
            logger.info("%s uses a hosted model; no local pipeline to load", self.provider)
            return None

        if self.provider == "storyboard":
            logger.info("storyboard uses local Pillow rendering; no pipeline to load")
            return None

        if self.pipeline is not None:
            logger.info("Using cached Stable Diffusion pipeline")
            return self.pipeline

        with self._load_lock:
            if self.pipeline is not None:
                logger.info("Using cached Stable Diffusion pipeline")
                return self.pipeline

            logger.info("Loading model...")
            logger.info(
                "Image generation model loading started: model=%s low_memory=%s",
                self.model_id,
                self.low_memory_mode,
            )

            try:
                import torch
                from diffusers import StableDiffusionPipeline
            except ImportError as exc:
                error_trace = traceback.format_exc()
                logger.exception("Model loading failed")
                logger.exception(traceback.format_exc())
                raise ModelLoadError(error_trace) from exc

            self._torch = torch
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            if self.device == "cpu":
                self._apply_cpu_generation_settings()

            torch_dtype = torch.float16 if self.device == "cuda" else torch.float32

            try:
                if self.device == "cpu":
                    torch.set_num_threads(self._env_int("CINEGEN_TORCH_THREADS", 4))
            except Exception as exc:
                error_trace = traceback.format_exc()
                logger.exception("Model loading failed")
                logger.exception(traceback.format_exc())
                raise ModelLoadError(error_trace) from exc

            try:
                pipeline = StableDiffusionPipeline.from_pretrained(
                    self.model_id,
                    torch_dtype=torch_dtype,
                )
            except Exception as exc:
                error_trace = traceback.format_exc()
                logger.exception("Model loading failed")
                logger.exception(traceback.format_exc())
                raise ModelLoadError(error_trace) from exc

            try:
                pipeline = pipeline.to(self.device)
            except Exception as exc:
                error_trace = traceback.format_exc()
                logger.exception("Model loading failed")
                logger.exception(traceback.format_exc())
                raise ModelLoadError(error_trace) from exc

            try:
                self._enable_memory_optimizations(pipeline)
                pipeline.set_progress_bar_config(disable=True)
            except Exception as exc:
                error_trace = traceback.format_exc()
                logger.exception("Model loading failed")
                logger.exception(traceback.format_exc())
                raise ModelLoadError(error_trace) from exc

            self.pipeline = pipeline
            logger.info("Model loaded successfully")
            logger.info(
                "Model loaded on %s: %s height=%s width=%s steps=%s guidance=%s timeout=%ss",
                self.device.upper(),
                self.model_id,
                self.image_height,
                self.image_width,
                self.num_inference_steps,
                self.guidance_scale,
                self.generation_timeout_seconds,
            )
            return self.pipeline

    def generate_image(
        self,
        prompt: str,
        scene_number: int,
    ) -> ImageResponse:
        """Generate a PNG image for one scene prompt and return its metadata."""
        prompt_text = self._validate_prompt(prompt)
        scene = self._validate_scene_number(scene_number)
        target_path = self._build_image_path(scene=scene)

        logger.info("Prompt received for scene %s: %s", scene, prompt_text)
        logger.info("Scene %s", scene)
        logger.info(
            "Image generation started for scene %s: path=%s width=%s height=%s steps=%s",
            scene,
            target_path.as_posix(),
            self.image_width,
            self.image_height,
            self.num_inference_steps,
        )
        started_at = perf_counter()

        if self.provider == "fal":
            try:
                return self._generate_fal_image(
                    prompt_text=prompt_text,
                    scene=scene,
                    target_path=target_path,
                    started_at=started_at,
                )
            except ImageGenerationError as exc:
                fallback_image = self._generate_hosted_fallback_image(
                    prompt_text=prompt_text,
                    scene=scene,
                    target_path=target_path,
                    previous_error=exc,
                )
                if fallback_image is not None:
                    return fallback_image

                raise

        if self.provider == "huggingface":
            try:
                return self._generate_huggingface_image(
                    prompt_text=prompt_text,
                    scene=scene,
                    target_path=target_path,
                    started_at=started_at,
                )
            except ImageGenerationError as exc:
                fallback_image = self._generate_hosted_fallback_image(
                    prompt_text=prompt_text,
                    scene=scene,
                    target_path=target_path,
                    previous_error=exc,
                )
                if fallback_image is not None:
                    return fallback_image

                raise

        if self.provider == "pollinations":
            try:
                return self._generate_pollinations_image(
                    prompt_text=prompt_text,
                    scene=scene,
                    target_path=target_path,
                    started_at=started_at,
                )
            except ImageGenerationError as exc:
                fallback_image = self._generate_hosted_fallback_image(
                    prompt_text=prompt_text,
                    scene=scene,
                    target_path=target_path,
                    previous_error=exc,
                )
                if fallback_image is not None:
                    return fallback_image

                raise

        if self.provider == "storyboard":
            return self._generate_storyboard_image(
                prompt_text=prompt_text,
                scene=scene,
                target_path=target_path,
                started_at=started_at,
            )

        return self._generate_stable_diffusion_image(
            prompt_text=prompt_text,
            scene=scene,
            target_path=target_path,
            started_at=started_at,
        )

    def _generate_stable_diffusion_image(
        self,
        prompt_text: str,
        scene: int,
        target_path: Path,
        started_at: float,
    ) -> ImageResponse:
        """Generate one image with the local Stable Diffusion pipeline."""
        pipeline = self.load_model()
        torch = self._require_torch()
        logger.info("Generating image...")

        try:
            with self._generation_lock:
                autocast_context = (
                    torch.autocast("cuda")
                    if self.device == "cuda"
                    else nullcontext()
                )
                with torch.inference_mode(), autocast_context:
                    result = self._run_pipeline_with_timeout(
                        pipeline=pipeline,
                        scene=scene,
                        started_at=started_at,
                        prompt=prompt_text,
                    )
                    self._raise_if_generation_timed_out(
                        scene=scene,
                        started_at=started_at,
                    )
                    image = result.images[0]
        except Exception as exc:
            error_trace = traceback.format_exc()
            logger.exception("Image generation failed")
            logger.exception(traceback.format_exc())
            raise ImageGenerationError(error_trace) from exc
        finally:
            self._release_cuda_memory()

        logger.info("Image generated")
        logger.info(
            "Image generation completed for scene %s in %.2fs",
            scene,
            perf_counter() - started_at,
        )
        logger.info("Saving image...")
        self._save_image(image=image, target_path=target_path, scene_number=scene)
        logger.info("Image saved: %s", target_path.as_posix())
        logger.info(
            "Generation completed in %.2f seconds",
            perf_counter() - started_at,
        )
        logger.info(
            "Image generation result ready for scene %s: status=success path=%s elapsed=%.2fs",
            scene,
            target_path.as_posix(),
            perf_counter() - started_at,
        )
        return ImageResponse(
            scene=scene,
            status="success",
            image_path=target_path.as_posix(),
            image_url=None,
            provider="stable-diffusion",
            warning=None,
            error=None,
        )

    def _generate_hosted_fallback_image(
        self,
        prompt_text: str,
        scene: int,
        target_path: Path,
        previous_error: Exception,
    ) -> ImageResponse | None:
        """Try configured hosted providers after the primary provider fails."""
        primary_error = previous_error
        for fallback_provider in self.fallback_providers:
            if fallback_provider == self.provider:
                continue

            fallback_started_at = perf_counter()
            logger.warning(
                "Primary image provider %s failed for scene %s; trying %s fallback: %s",
                self.provider,
                scene,
                fallback_provider,
                self._build_user_error_message(previous_error),
            )

            try:
                if fallback_provider == "pollinations":
                    return self._generate_pollinations_image(
                        prompt_text=prompt_text,
                        scene=scene,
                        target_path=target_path,
                        started_at=fallback_started_at,
                    )

                if fallback_provider == "fal":
                    return self._generate_fal_image(
                        prompt_text=prompt_text,
                        scene=scene,
                        target_path=target_path,
                        started_at=fallback_started_at,
                    )

                if fallback_provider == "storyboard":
                    return self._generate_storyboard_image(
                        prompt_text=prompt_text,
                        scene=scene,
                        target_path=target_path,
                        started_at=fallback_started_at,
                        warning=self._build_fallback_warning(
                            primary_error=primary_error,
                            last_error=previous_error,
                        ),
                    )
            except Exception as exc:
                logger.exception(
                    "Fallback image provider %s failed for scene %s",
                    fallback_provider,
                    scene,
                )
                logger.exception(traceback.format_exc())
                previous_error = exc

        return None

    def _build_fallback_warning(
        self,
        primary_error: Exception,
        last_error: Exception,
    ) -> str:
        """Build a concise warning for locally rendered storyboard fallbacks."""
        primary_message = self._build_user_error_message(primary_error)
        last_message = self._build_user_error_message(last_error)
        warning = (
            "Hosted image providers failed, so CineGen rendered a local storyboard "
            f"fallback. Primary provider error: {primary_message}"
        )

        if last_message != primary_message:
            warning = f"{warning} Last fallback error: {last_message}"

        return warning

    def _generate_storyboard_image(
        self,
        prompt_text: str,
        scene: int,
        target_path: Path,
        started_at: float,
        warning: str | None = None,
    ) -> ImageResponse:
        """Generate a local illustrated storyboard panel for one scene."""
        logger.info("Rendering local storyboard image for scene %s", scene)

        try:
            image = self._create_storyboard_panel(prompt_text=prompt_text, scene=scene)
            self._raise_if_generation_timed_out(scene=scene, started_at=started_at)
        except Exception as exc:
            error_trace = traceback.format_exc()
            logger.exception("Local storyboard image rendering failed")
            logger.exception(traceback.format_exc())
            raise ImageGenerationError(error_trace) from exc

        self._save_image(image=image, target_path=target_path, scene_number=scene)
        logger.info(
            "Local storyboard image ready for scene %s: path=%s elapsed=%.2fs",
            scene,
            target_path.as_posix(),
            perf_counter() - started_at,
        )
        return ImageResponse(
            scene=scene,
            status="success",
            image_path=target_path.as_posix(),
            image_url=None,
            provider="storyboard",
            warning=warning,
            error=None,
        )

    def _generate_huggingface_image(
        self,
        prompt_text: str,
        scene: int,
        target_path: Path,
        started_at: float,
    ) -> ImageResponse:
        """Generate one image with Hugging Face Inference Providers."""
        logger.info(
            "Calling Hugging Face for scene %s: model=%s provider=%s width=%s height=%s steps=%s",
            scene,
            self.hf_model_id,
            self.hf_provider,
            self.image_width,
            self.image_height,
            self.num_inference_steps,
        )

        try:
            image = self._call_huggingface_image(prompt_text)
            self._raise_if_generation_timed_out(scene=scene, started_at=started_at)
        except Exception as exc:
            error_trace = traceback.format_exc()
            logger.exception("Hugging Face image generation failed")
            logger.exception(traceback.format_exc())
            raise ImageGenerationError(error_trace) from exc

        logger.info("Image generated")
        logger.info(
            "Image generation completed for scene %s in %.2fs",
            scene,
            perf_counter() - started_at,
        )
        logger.info("Saving image...")
        self._save_image(image=image, target_path=target_path, scene_number=scene)
        logger.info("Image saved: %s", target_path.as_posix())
        logger.info(
            "Generation completed in %.2f seconds",
            perf_counter() - started_at,
        )
        logger.info(
            "Image generation result ready for scene %s: status=success path=%s elapsed=%.2fs",
            scene,
            target_path.as_posix(),
            perf_counter() - started_at,
        )
        return ImageResponse(
            scene=scene,
            status="success",
            image_path=target_path.as_posix(),
            image_url=None,
            provider="huggingface",
            warning=None,
            error=None,
        )

    def _generate_pollinations_image(
        self,
        prompt_text: str,
        scene: int,
        target_path: Path,
        started_at: float,
    ) -> ImageResponse:
        """Generate one image with Pollinations and save it as a local PNG."""
        logger.info(
            "Calling Pollinations for scene %s: model=%s size=%s quality=%s",
            scene,
            self.pollinations_model_id,
            self.pollinations_image_size,
            self.pollinations_quality,
        )

        try:
            result = self._call_pollinations_image(prompt_text)
            image_bytes = self._extract_pollinations_image_bytes(result)
            self._raise_if_generation_timed_out(scene=scene, started_at=started_at)
        except Exception as exc:
            error_trace = traceback.format_exc()
            logger.exception("Pollinations image generation failed")
            logger.exception(traceback.format_exc())
            raise ImageGenerationError(error_trace) from exc

        logger.info("Image generated")
        logger.info(
            "Image generation completed for scene %s in %.2fs",
            scene,
            perf_counter() - started_at,
        )
        logger.info("Saving image...")
        self._save_image_bytes(
            image_bytes=image_bytes,
            target_path=target_path,
            scene_number=scene,
        )
        logger.info("Image saved: %s", target_path.as_posix())
        logger.info(
            "Generation completed in %.2f seconds",
            perf_counter() - started_at,
        )
        logger.info(
            "Image generation result ready for scene %s: status=success path=%s elapsed=%.2fs",
            scene,
            target_path.as_posix(),
            perf_counter() - started_at,
        )
        return ImageResponse(
            scene=scene,
            status="success",
            image_path=target_path.as_posix(),
            image_url=None,
            provider="pollinations",
            warning=None,
            error=None,
        )

    def _generate_fal_image(
        self,
        prompt_text: str,
        scene: int,
        target_path: Path,
        started_at: float,
    ) -> ImageResponse:
        """Generate one image with fal.ai FLUX and save it as a local PNG."""
        logger.info(
            "Calling fal.ai FLUX for scene %s: model=%s image_size=%s steps=%s",
            scene,
            self.fal_model_id,
            self.fal_image_size,
            self.fal_num_inference_steps,
        )

        try:
            result = self._call_fal_flux(prompt_text)
            image_bytes = self._extract_fal_image_bytes(result)
            self._raise_if_generation_timed_out(scene=scene, started_at=started_at)
        except Exception as exc:
            error_trace = traceback.format_exc()
            logger.exception("fal.ai FLUX image generation failed")
            logger.exception(traceback.format_exc())
            raise ImageGenerationError(error_trace) from exc

        logger.info("Image generated")
        logger.info(
            "Image generation completed for scene %s in %.2fs",
            scene,
            perf_counter() - started_at,
        )
        logger.info("Saving image...")
        self._save_image_bytes(
            image_bytes=image_bytes,
            target_path=target_path,
            scene_number=scene,
        )
        logger.info("Image saved: %s", target_path.as_posix())
        logger.info(
            "Generation completed in %.2f seconds",
            perf_counter() - started_at,
        )
        logger.info(
            "Image generation result ready for scene %s: status=success path=%s elapsed=%.2fs",
            scene,
            target_path.as_posix(),
            perf_counter() - started_at,
        )
        return ImageResponse(
            scene=scene,
            status="success",
            image_path=target_path.as_posix(),
            image_url=None,
            provider="fal",
            warning=None,
            error=None,
        )

    def generate_images(
        self,
        prompts: Iterable[Prompt | dict[str, Any]],
    ) -> list[ImageResponse]:
        """Generate images for every prompt while preserving partial results."""
        prompt_items = list(prompts)
        if not self._batch_lock.acquire(blocking=False):
            logger.warning(
                "Image batch rejected because another image batch is already running"
            )
            return self._busy_responses(prompt_items)

        try:
            return self._generate_images_locked(prompt_items)
        finally:
            self._batch_lock.release()

    def generate_image_with_fallback(
        self,
        prompt: str,
        scene_number: int,
    ) -> ImageResponse:
        """Generate one scene image and save a placeholder when generation fails."""
        try:
            return self.generate_image(prompt=prompt, scene_number=scene_number)
        except ModelLoadError as exc:
            logger.exception("Model loading failed")
            logger.exception(traceback.format_exc())
            return self._failed_response(scene_number, exc, save_placeholder=False)
        except ImageSaveError as exc:
            logger.exception("Image saving failed")
            logger.exception(traceback.format_exc())
            return self._failed_response(scene_number, exc, save_placeholder=False)
        except ImageGenerationError as exc:
            logger.exception("Image generation failed")
            logger.exception(traceback.format_exc())
            return self._failed_response(scene_number, exc)
        except Exception as exc:
            error_trace = traceback.format_exc()
            logger.exception("Image generation failed")
            logger.exception(traceback.format_exc())
            return self._failed_response(
                scene_number,
                ImageGenerationError(error_trace),
            )

    def build_failed_images(
        self,
        prompts: Iterable[Prompt | dict[str, Any]],
        error: Exception | str,
    ) -> list[ImageResponse]:
        """Build failed image records and save one placeholder PNG per prompt."""
        failed_images: list[ImageResponse] = []

        for fallback_scene, prompt_item in enumerate(prompts, start=1):
            try:
                _, scene_number = self._coerce_prompt(prompt_item)
            except Exception:
                scene_number = fallback_scene

            failed_images.append(self._failed_response(scene_number, error))

        return failed_images

    def save_placeholder_image(
        self,
        scene_number: int,
        error_message: str,
        target_path: str | Path | None = None,
    ) -> str | None:
        """Save a placeholder PNG for a scene and return its image path."""
        scene = self._validate_scene_number(scene_number)
        placeholder_path = Path(target_path) if target_path else self._build_image_path(scene)

        if self._save_placeholder_image(
            target_path=placeholder_path,
            scene_number=scene,
            error_message=error_message,
        ):
            return placeholder_path.as_posix()

        return None

    def _generate_images_locked(
        self,
        prompt_items: list[Prompt | dict[str, Any]],
    ) -> list[ImageResponse]:
        """Generate an image batch while the batch lock is held."""
        images: list[ImageResponse] = []

        logger.info(
            "Image batch started: scenes=%s output_dir=%s",
            len(prompt_items),
            self.output_dir.as_posix(),
        )

        for index, prompt_item in enumerate(prompt_items, start=1):
            scene_number = index

            try:
                prompt_text, scene_number = self._coerce_prompt(prompt_item)
                images.append(
                    self.generate_image(
                        prompt=prompt_text,
                        scene_number=scene_number,
                    )
                )
            except ModelLoadError as exc:
                logger.exception("Model loading failed")
                logger.exception(traceback.format_exc())
                images.append(
                    self._failed_response(
                        scene_number,
                        exc,
                        save_placeholder=False,
                    )
                )
                images.extend(
                    self._failed_responses_for_remaining_prompts(
                        prompt_items=prompt_items,
                        start_index=index,
                        error=exc,
                        save_placeholder=False,
                    )
                )
                break
            except ImageSaveError as exc:
                logger.exception("Image saving failed")
                logger.exception(traceback.format_exc())
                images.append(
                    self._failed_response(
                        scene_number,
                        exc,
                        save_placeholder=False,
                    )
                )
            except ImageGenerationError as exc:
                logger.exception("Image generation failed")
                logger.exception(traceback.format_exc())
                images.append(self._failed_response(scene_number, exc))
            except Exception as exc:
                error_trace = traceback.format_exc()
                logger.exception("Image generation failed")
                logger.exception(traceback.format_exc())
                images.append(
                    self._failed_response(
                        scene_number,
                        ImageGenerationError(error_trace),
                    )
                )

        succeeded = sum(1 for image in images if image.status == "success")
        failed = sum(1 for image in images if image.status == "failed")
        logger.info(
            "Image batch finished: succeeded=%s failed=%s",
            succeeded,
            failed,
        )

        return images

    def _busy_responses(
        self,
        prompt_items: list[Prompt | dict[str, Any]],
    ) -> list[ImageResponse]:
        """Return fast failures when another image batch is already in progress."""
        busy_error = ImageGenerationError(
            "Another image generation batch is already running. Try again later."
        )
        failed_images: list[ImageResponse] = []

        for fallback_scene, prompt_item in enumerate(prompt_items, start=1):
            try:
                _, scene_number = self._coerce_prompt(prompt_item)
            except Exception:
                scene_number = fallback_scene

            failed_images.append(
                self._failed_response(
                    scene_number,
                    busy_error,
                    save_placeholder=False,
                )
            )

        return failed_images

    def _call_huggingface_image(self, prompt: str) -> Any:
        """Call the configured Hugging Face text-to-image model."""
        api_key = self._get_huggingface_key()

        try:
            from huggingface_hub import InferenceClient
        except ImportError as exc:
            raise ModelLoadError(
                "huggingface-hub is not installed. Run: pip install -r requirements.txt"
            ) from exc

        client = InferenceClient(
            model=self.hf_model_id,
            provider=self._huggingface_provider_value(),
            api_key=api_key,
            timeout=self.hf_timeout_seconds,
        )
        return client.text_to_image(
            prompt,
            **self._build_huggingface_arguments(),
        )

    def _get_huggingface_key(self) -> str:
        """Read the Hugging Face token from supported environment names."""
        api_key = (
            os.getenv("HF_TOKEN")
            or os.getenv("HUGGINGFACEHUB_API_TOKEN")
            or os.getenv("CINEGEN_HF_TOKEN")
            or os.getenv("CINEGEN_HUGGINGFACE_TOKEN")
        )
        if not api_key:
            raise ImageGenerationError(
                "HF_TOKEN is required for Hugging Face image generation."
            )

        return api_key

    def _huggingface_provider_value(self) -> str | None:
        """Return the configured Hugging Face provider selector."""
        provider = self.hf_provider.strip()
        if not provider or provider.lower() in {"none", "default"}:
            return None

        return provider

    def _build_huggingface_arguments(self) -> dict[str, Any]:
        """Build Hugging Face text-to-image request arguments."""
        arguments: dict[str, Any] = {
            "height": self.image_height,
            "width": self.image_width,
            "num_inference_steps": self.num_inference_steps,
            "guidance_scale": self.guidance_scale,
        }

        if self.hf_negative_prompt:
            arguments["negative_prompt"] = self.hf_negative_prompt

        return arguments

    def _call_pollinations_image(self, prompt: str) -> dict[str, Any]:
        """Call the Pollinations OpenAI-compatible image generation endpoint."""
        api_key = self._get_pollinations_key()
        endpoint = f"{self.pollinations_base_url}/v1/images/generations"
        payload = json.dumps(self._build_pollinations_arguments(prompt)).encode("utf-8")
        request = UrlRequest(
            endpoint,
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "CineGenAI/1.0",
            },
            method="POST",
        )

        try:
            with urlopen(
                request,
                timeout=self.pollinations_timeout_seconds,
            ) as response:
                response_body = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = self._read_http_error_detail(exc)
            raise ImageGenerationError(
                f"Pollinations request failed with HTTP {exc.code}: {detail}"
            ) from exc
        except URLError as exc:
            raise ImageGenerationError(f"Pollinations request failed: {exc}") from exc

        try:
            parsed_response = json.loads(response_body)
        except json.JSONDecodeError as exc:
            raise ImageGenerationError(
                "Pollinations returned an invalid JSON response."
            ) from exc

        if not isinstance(parsed_response, dict):
            raise ImageGenerationError("Pollinations response payload is invalid.")

        return parsed_response

    def _get_pollinations_key(self) -> str:
        """Read the Pollinations API key from supported environment names."""
        api_key = os.getenv("POLLINATIONS_KEY") or os.getenv("CINEGEN_POLLINATIONS_KEY")
        if not api_key:
            raise ImageGenerationError(
                "POLLINATIONS_KEY is required for Pollinations image generation."
            )

        return api_key

    def _build_pollinations_arguments(self, prompt: str) -> dict[str, Any]:
        """Build the Pollinations image generation request body."""
        return {
            "prompt": prompt,
            "model": self.pollinations_model_id,
            "n": 1,
            "size": self.pollinations_image_size,
            "quality": self.pollinations_quality,
            "response_format": "b64_json",
            "safe": self._pollinations_safe_value(),
            "user": "cinegen-ai",
        }

    def _pollinations_safe_value(self) -> str | bool:
        """Return the configured Pollinations safety value."""
        raw_value = self.pollinations_safe.strip()
        lowered = raw_value.lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True

        if lowered in {"false", "0", "no", "off"}:
            return False

        return raw_value

    def _extract_pollinations_image_bytes(self, result: dict[str, Any]) -> bytes:
        """Read generated image bytes from a Pollinations response payload."""
        image_items = result.get("data")
        if not image_items:
            raise ImageGenerationError("Pollinations response did not include images.")

        first_image = image_items[0]
        if not isinstance(first_image, dict):
            raise ImageGenerationError("Pollinations image payload is invalid.")

        b64_json = first_image.get("b64_json")
        if isinstance(b64_json, str) and b64_json:
            return base64.b64decode(b64_json)

        image_url = str(first_image.get("url") or "")
        if image_url:
            return self._read_remote_image_url(
                image_url,
                timeout=self.pollinations_timeout_seconds,
            )

        raise ImageGenerationError("Pollinations image response is missing image data.")

    def _read_http_error_detail(self, error: HTTPError) -> str:
        """Read a concise HTTP error body without exposing credentials."""
        try:
            detail = error.read().decode("utf-8", errors="replace").strip()
        except Exception:
            detail = str(error)

        return detail[:1000] if detail else str(error)

    def _call_fal_flux(self, prompt: str) -> dict[str, Any]:
        """Call the configured fal.ai FLUX endpoint."""
        self._configure_fal_credentials()

        try:
            import fal_client
        except ImportError as exc:
            raise ModelLoadError(
                "fal-client is not installed. Run: pip install -r requirements.txt"
            ) from exc

        arguments = self._build_fal_arguments(prompt)
        return fal_client.subscribe(self.fal_model_id, arguments=arguments)

    def _configure_fal_credentials(self) -> None:
        """Make fal credentials available to the Python client."""
        if os.getenv("FAL_KEY"):
            return

        cinegen_fal_key = os.getenv("CINEGEN_FAL_KEY")
        if cinegen_fal_key:
            os.environ["FAL_KEY"] = cinegen_fal_key
            return

        raise ImageGenerationError(
            "FAL_KEY is required for fal.ai FLUX image generation."
        )

    def _build_fal_arguments(self, prompt: str) -> dict[str, Any]:
        """Build fal.ai FLUX request arguments from environment settings."""
        arguments: dict[str, Any] = {
            "prompt": prompt,
            "image_size": self._build_fal_image_size(),
            "num_inference_steps": self.fal_num_inference_steps,
            "guidance_scale": self.fal_guidance_scale,
            "num_images": 1,
            "enable_safety_checker": self.fal_enable_safety_checker,
            "output_format": self.fal_output_format,
            "sync_mode": self.fal_sync_mode,
        }

        if self.fal_acceleration:
            arguments["acceleration"] = self.fal_acceleration

        return arguments

    def _build_fal_image_size(self) -> str | dict[str, int]:
        """Return a fal image_size enum or custom width/height object."""
        raw_size = self.fal_image_size.strip()
        if raw_size.lower() == "custom":
            return {"width": self.image_width, "height": self.image_height}

        if "x" in raw_size.lower():
            width_text, height_text = raw_size.lower().split("x", 1)
            try:
                return {"width": int(width_text), "height": int(height_text)}
            except ValueError:
                logger.warning(
                    "Invalid CINEGEN_FAL_IMAGE_SIZE=%r; using landscape_16_9",
                    self.fal_image_size,
                )
                return "landscape_16_9"

        return raw_size

    def _extract_fal_image_bytes(self, result: dict[str, Any]) -> bytes:
        """Read generated image bytes from a fal result payload."""
        images = result.get("images") if isinstance(result, dict) else None
        if not images:
            raise ImageGenerationError("fal.ai response did not include images.")

        first_image = images[0]
        if not isinstance(first_image, dict):
            raise ImageGenerationError("fal.ai response image payload is invalid.")

        image_url = str(first_image.get("url") or "")
        if not image_url:
            raise ImageGenerationError("fal.ai response image URL is missing.")

        return self._read_fal_image_url(image_url)

    def _read_fal_image_url(self, image_url: str) -> bytes:
        """Read a fal image URL or data URI into bytes."""
        if image_url.startswith("data:"):
            return self._decode_data_uri(image_url)

        return self._read_remote_image_url(
            image_url,
            timeout=self.fal_download_timeout_seconds,
        )

    def _read_remote_image_url(self, image_url: str, timeout: float) -> bytes:
        """Read a remote image URL into bytes."""
        request = UrlRequest(
            image_url,
            headers={"User-Agent": "CineGenAI/1.0"},
        )
        with urlopen(request, timeout=timeout) as response:
            return response.read()

    def _decode_data_uri(self, data_uri: str) -> bytes:
        """Decode a data URI returned by fal sync mode."""
        try:
            metadata, payload = data_uri.split(",", 1)
        except ValueError as exc:
            raise ImageGenerationError("fal.ai returned an invalid data URI.") from exc

        if ";base64" in metadata:
            return base64.b64decode(payload)

        return unquote_to_bytes(payload)

    def _enable_memory_optimizations(self, pipeline: Any) -> None:
        """Enable low-risk memory optimizations supported by diffusers."""
        if not self.low_memory_mode:
            return

        try:
            pipeline.enable_attention_slicing()
        except Exception:
            logger.debug("Attention slicing is unavailable for this pipeline")

        try:
            pipeline.enable_vae_slicing()
        except Exception:
            logger.debug("VAE slicing is unavailable for this pipeline")

        try:
            pipeline.enable_vae_tiling()
        except Exception:
            logger.debug("VAE tiling is unavailable for this pipeline")

    def _apply_cpu_generation_settings(self) -> None:
        """Use lightweight Stable Diffusion settings when no CUDA device exists."""
        self.image_height = 192
        self.image_width = 192
        self.num_inference_steps = 6
        self.guidance_scale = 5.5
        logger.info("CPU mode detected. Using ultra-light settings.")

    def _run_pipeline_with_timeout(
        self,
        pipeline: Any,
        scene: int,
        started_at: float,
        prompt: str,
    ) -> Any:
        """Run Stable Diffusion with a per-step timeout watchdog."""
        pipeline_kwargs = {
            "prompt": prompt,
            "height": self.image_height,
            "width": self.image_width,
            "num_inference_steps": self.num_inference_steps,
            "guidance_scale": self.guidance_scale,
        }
        logger.info(
            (
                "Calling Stable Diffusion pipeline for scene %s: "
                "height=%s width=%s num_inference_steps=%s guidance_scale=%s"
            ),
            scene,
            self.image_height,
            self.image_width,
            self.num_inference_steps,
            self.guidance_scale,
        )

        if self.generation_timeout_seconds <= 0:
            return pipeline(**pipeline_kwargs)

        def callback_on_step_end(
            pipeline_instance: Any,
            step: int,
            timestep: Any,
            callback_kwargs: dict[str, Any],
        ) -> dict[str, Any]:
            self._raise_if_generation_timed_out(scene=scene, started_at=started_at)
            return callback_kwargs

        try:
            return pipeline(
                **pipeline_kwargs,
                callback_on_step_end=callback_on_step_end,
                callback_on_step_end_tensor_inputs=["latents"],
            )
        except TypeError as exc:
            if "callback_on_step_end" not in str(exc):
                raise

            logger.debug(
                "callback_on_step_end unsupported; using legacy Stable Diffusion callback for scene %s",
                scene,
            )

        def legacy_callback(step: int, timestep: Any, latents: Any) -> None:
            self._raise_if_generation_timed_out(scene=scene, started_at=started_at)

        return pipeline(
            **pipeline_kwargs,
            callback=legacy_callback,
            callback_steps=1,
        )

    def _raise_if_generation_timed_out(self, scene: int, started_at: float) -> None:
        """Raise when the active image generation has exceeded its timeout."""
        elapsed = perf_counter() - started_at
        if elapsed <= self.generation_timeout_seconds:
            return

        raise GenerationTimeoutError(
            (
                f"Image generation timed out for scene {scene} after "
                f"{elapsed:.2f} seconds."
            )
        )

    def _save_image(self, image: Any, target_path: Path, scene_number: int) -> None:
        """Save a PIL image to the configured output directory."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        try:
            image.save(target_path, format="PNG")
        except Exception as exc:
            error_trace = traceback.format_exc()
            logger.exception("Image saving failed")
            logger.exception(traceback.format_exc())
            raise ImageSaveError(error_trace) from exc

        logger.info(
            "Image saved for scene %s: %s",
            scene_number,
            target_path.as_posix(),
        )

    def _save_image_bytes(
        self,
        image_bytes: bytes,
        target_path: Path,
        scene_number: int,
    ) -> None:
        """Convert returned image bytes to a PNG file at the target path."""
        try:
            from PIL import Image
        except ImportError as exc:
            raise ImageSaveError(
                "Pillow is required to save fal.ai image responses."
            ) from exc

        try:
            with Image.open(BytesIO(image_bytes)) as image:
                if image.mode not in {"RGB", "RGBA"}:
                    image = image.convert("RGB")

                self._save_image(
                    image=image,
                    target_path=target_path,
                    scene_number=scene_number,
                )
        except ImageSaveError:
            raise
        except Exception as exc:
            error_trace = traceback.format_exc()
            logger.exception("Image saving failed")
            logger.exception(traceback.format_exc())
            raise ImageSaveError(error_trace) from exc

    def _create_storyboard_panel(self, prompt_text: str, scene: int) -> Any:
        """Create a local cinematic panel when hosted providers are unavailable."""
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError as exc:
            raise ImageSaveError("Pillow is required to render storyboard images.") from exc

        width = max(256, int(self.image_width))
        height = max(256, int(self.image_height))
        seed = sum(ord(character) for character in prompt_text) + scene * 97
        environment = self._storyboard_environment(prompt_text)
        top_color, accent_color, glow_color = self._storyboard_palette(
            environment=environment,
            seed=seed,
        )
        image = Image.new("RGB", (width, height), top_color)
        draw = ImageDraw.Draw(image, "RGBA")

        self._draw_storyboard_background(
            draw,
            width,
            height,
            top_color,
            accent_color,
            glow_color,
            environment,
        )
        self._draw_storyboard_subject(draw, prompt_text, width, height, accent_color, glow_color)
        self._draw_storyboard_frame(draw, width, height, scene, glow_color)
        self._draw_storyboard_caption(draw, prompt_text, width, height)
        return image

    def _storyboard_environment(self, prompt_text: str) -> str:
        """Infer a local storyboard background from the prompt."""
        lowered_prompt = prompt_text.lower()
        environment_keywords: tuple[tuple[str, tuple[str, ...]], ...] = (
            ("space", ("space", "spaceship", "astronaut", "planet", "rocket", "star")),
            ("ocean", ("ocean", "sea", "beach", "island", "ship", "pirate", "harbor", "mermaid")),
            ("river", ("river", "waterfall", "lake")),
            ("future", ("robot", "machine", "future", "lab", "workshop")),
            ("town", ("city", "street", "town", "road", "shop", "school", "park")),
            ("indoor", ("home", "house", "room", "kitchen", "bedroom", "library", "museum", "classroom")),
            ("desert", ("desert", "sand", "dune")),
            ("cave", ("cave", "underground")),
            ("garden", ("garden", "flower", "meadow", "farm")),
            ("castle", ("castle", "kingdom", "princess", "prince", "queen", "wizard")),
            ("forest", ("forest", "woods", "jungle", "tree")),
            ("mountain", ("mountain", "snow")),
        )

        for environment, keywords in environment_keywords:
            if any(self._prompt_has_keyword(lowered_prompt, keyword) for keyword in keywords):
                return environment

        return "storybook"

    def _prompt_has_keyword(self, lowered_prompt: str, keyword: str) -> bool:
        """Match a prompt keyword without accidental substring hits."""
        lowered_keyword = keyword.lower()
        if " " in lowered_keyword:
            return lowered_keyword in lowered_prompt

        return re.search(
            rf"(?<![a-z0-9]){re.escape(lowered_keyword)}(?![a-z0-9])",
            lowered_prompt,
        ) is not None

    def _storyboard_palette(
        self,
        environment: str,
        seed: int,
    ) -> tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]:
        """Return a palette matched to the inferred storyboard environment."""
        palettes_by_environment: dict[
            str,
            tuple[tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]], ...],
        ] = {
            "castle": (
                ((88, 28, 135), (244, 114, 182), (254, 240, 138)),
                ((67, 56, 202), (192, 132, 252), (250, 245, 255)),
            ),
            "forest": (
                ((20, 83, 45), (74, 222, 128), (240, 253, 244)),
                ((22, 101, 52), (132, 204, 22), (236, 253, 245)),
            ),
            "ocean": (
                ((14, 116, 144), (45, 212, 191), (240, 253, 250)),
                ((30, 64, 175), (125, 211, 252), (240, 249, 255)),
            ),
            "river": (
                ((30, 64, 175), (45, 212, 191), (240, 249, 255)),
                ((21, 94, 117), (103, 232, 249), (236, 254, 255)),
            ),
            "town": (
                ((124, 45, 18), (251, 146, 60), (255, 247, 237)),
                ((30, 64, 175), (250, 204, 21), (254, 252, 232)),
            ),
            "indoor": (
                ((120, 53, 15), (251, 191, 36), (255, 251, 235)),
                ((67, 56, 202), (251, 207, 232), (253, 242, 248)),
            ),
            "future": (
                ((15, 23, 42), (56, 189, 248), (224, 242, 254)),
                ((49, 46, 129), (129, 140, 248), (238, 242, 255)),
            ),
            "space": (
                ((17, 24, 39), (99, 102, 241), (224, 231, 255)),
                ((30, 27, 75), (168, 85, 247), (245, 243, 255)),
            ),
            "desert": (
                ((146, 64, 14), (251, 191, 36), (255, 251, 235)),
                ((127, 29, 29), (251, 146, 60), (255, 247, 237)),
            ),
            "cave": (
                ((30, 41, 59), (14, 165, 233), (224, 242, 254)),
                ((76, 29, 149), (45, 212, 191), (240, 253, 250)),
            ),
            "garden": (
                ((21, 128, 61), (244, 114, 182), (240, 253, 244)),
                ((77, 124, 15), (250, 204, 21), (254, 252, 232)),
            ),
            "mountain": (
                ((30, 64, 175), (147, 197, 253), (239, 246, 255)),
                ((51, 65, 85), (186, 230, 253), (248, 250, 252)),
            ),
            "storybook": (
                ((31, 41, 55), (96, 165, 250), (248, 250, 252)),
                ((76, 29, 149), (244, 114, 182), (254, 240, 138)),
            ),
        }
        palettes = palettes_by_environment.get(environment, palettes_by_environment["storybook"])
        return palettes[seed % len(palettes)]

    def _draw_storyboard_background(
        self,
        draw: Any,
        width: int,
        height: int,
        top_color: tuple[int, int, int],
        accent_color: tuple[int, int, int],
        glow_color: tuple[int, int, int],
        environment: str,
    ) -> None:
        """Draw a storyboard background matched to the scene prompt."""
        for y in range(height):
            blend = y / max(1, height - 1)
            color = tuple(
                int(top_color[index] * (1 - blend) + accent_color[index] * blend * 0.75)
                for index in range(3)
            )
            draw.line([(0, y), (width, y)], fill=(*color, 255))

        horizon = int(height * 0.66)
        draw.ellipse(
            (int(width * 0.66), int(height * 0.09), int(width * 0.86), int(height * 0.29)),
            fill=(*glow_color, 115),
        )

        if environment == "space":
            for index in range(28):
                x = int(width * ((index * 37) % 100) / 100)
                y = int(height * (0.08 + ((index * 19) % 48) / 100))
                draw.ellipse((x, y, x + 3, y + 3), fill=(*glow_color, 210))
            draw.ellipse(
                (int(width * 0.12), int(height * 0.18), int(width * 0.34), int(height * 0.4)),
                fill=(*accent_color, 155),
                outline=(*glow_color, 160),
                width=3,
            )
            draw.rectangle((0, horizon, width, height), fill=(15, 23, 42, 155))
            return

        if environment == "ocean":
            draw.rectangle((0, horizon, width, height), fill=(14, 116, 144, 150))
            for index in range(5):
                y = horizon + int(height * (0.05 + index * 0.055))
                draw.arc(
                    (int(width * -0.05), y, int(width * 1.05), y + int(height * 0.18)),
                    180,
                    360,
                    fill=(*glow_color, 145),
                    width=3,
                )
            draw.polygon(
                [
                    (int(width * 0.1), horizon),
                    (int(width * 0.25), int(height * 0.5)),
                    (int(width * 0.42), horizon),
                ],
                fill=(34, 197, 94, 145),
            )
            return

        if environment == "river":
            draw.rectangle((0, horizon, width, height), fill=(22, 101, 52, 120))
            draw.polygon(
                [
                    (int(width * 0.35), horizon),
                    (int(width * 0.58), horizon),
                    (int(width * 0.86), height),
                    (int(width * 0.13), height),
                ],
                fill=(14, 165, 233, 150),
            )
            for index in range(4):
                y = horizon + int(height * (0.08 + index * 0.07))
                draw.line(
                    (int(width * 0.24), y, int(width * 0.76), y + int(height * 0.04)),
                    fill=(*glow_color, 120),
                    width=2,
                )
            return

        if environment == "town":
            draw.rectangle((0, horizon, width, height), fill=(71, 85, 105, 135))
            for index, x in enumerate(range(int(width * 0.05), width, max(46, width // 5))):
                building_height = int(height * (0.22 + (index % 3) * 0.06))
                draw.rounded_rectangle(
                    (x, horizon - building_height, x + int(width * 0.16), horizon + 8),
                    radius=6,
                    fill=(*glow_color, 140),
                    outline=(*accent_color, 170),
                    width=2,
                )
                draw.rectangle(
                    (x + 8, horizon - int(building_height * 0.45), x + int(width * 0.16) - 8, horizon - int(building_height * 0.28)),
                    fill=(*accent_color, 150),
                )
            draw.polygon(
                [
                    (int(width * 0.44), horizon),
                    (int(width * 0.56), horizon),
                    (int(width * 0.75), height),
                    (int(width * 0.25), height),
                ],
                fill=(15, 23, 42, 115),
            )
            return

        if environment == "indoor":
            draw.rectangle((0, int(height * 0.45), width, height), fill=(120, 53, 15, 95))
            draw.rectangle(
                (int(width * 0.1), int(height * 0.13), int(width * 0.34), int(height * 0.42)),
                fill=(*glow_color, 130),
                outline=(*accent_color, 170),
                width=3,
            )
            draw.line((0, int(height * 0.45), width, int(height * 0.45)), fill=(*glow_color, 95), width=3)
            draw.rounded_rectangle(
                (int(width * 0.62), int(height * 0.22), int(width * 0.86), int(height * 0.72)),
                radius=8,
                fill=(15, 23, 42, 90),
                outline=(*glow_color, 120),
                width=2,
            )
            return

        if environment == "future":
            draw.rectangle((0, horizon, width, height), fill=(15, 23, 42, 135))
            for index in range(6):
                x = int(width * (0.08 + index * 0.16))
                draw.line((x, int(height * 0.18), x, height), fill=(*glow_color, 70), width=2)
            for index in range(4):
                y = int(height * (0.22 + index * 0.13))
                draw.line((0, y, width, y + int(height * 0.04)), fill=(*accent_color, 65), width=3)
            draw.rounded_rectangle(
                (int(width * 0.12), int(height * 0.2), int(width * 0.32), int(height * 0.42)),
                radius=10,
                fill=(*glow_color, 85),
                outline=(*accent_color, 160),
                width=2,
            )
            return

        if environment == "desert":
            draw.rectangle((0, horizon, width, height), fill=(251, 191, 36, 115))
            for index in range(3):
                y = horizon + int(height * (0.02 + index * 0.08))
                draw.arc(
                    (int(width * -0.1), y, int(width * 1.1), y + int(height * 0.28)),
                    180,
                    360,
                    fill=(*glow_color, 95),
                    width=4,
                )
            return

        if environment == "cave":
            draw.rectangle((0, horizon, width, height), fill=(15, 23, 42, 160))
            draw.ellipse(
                (int(width * -0.1), int(height * 0.18), int(width * 1.1), int(height * 1.15)),
                outline=(15, 23, 42, 190),
                width=max(24, width // 11),
            )
            for index in range(6):
                x = int(width * (0.16 + index * 0.13))
                draw.polygon(
                    [
                        (x, int(height * 0.76)),
                        (x - int(width * 0.035), int(height * 0.58)),
                        (x + int(width * 0.045), int(height * 0.64)),
                    ],
                    fill=(*glow_color, 130),
                )
            return

        if environment == "garden":
            draw.rectangle((0, horizon, width, height), fill=(22, 163, 74, 120))
            for index in range(14):
                x = int(width * (0.08 + (index * 0.07) % 0.86))
                y = int(height * (0.67 + (index % 4) * 0.05))
                draw.ellipse((x, y, x + 10, y + 10), fill=(*accent_color, 185))
                draw.line((x + 5, y + 10, x + 5, y + 24), fill=(22, 101, 52, 190), width=2)
            return

        if environment == "forest":
            draw.rectangle((0, horizon, width, height), fill=(20, 83, 45, 135))
            for index, x in enumerate(range(int(width * 0.06), width, max(36, width // 8))):
                tree_top = int(height * (0.25 + (index % 3) * 0.04))
                draw.rectangle((x - 6, tree_top + 30, x + 6, horizon + 14), fill=(64, 35, 20, 185))
                draw.polygon(
                    [
                        (x, tree_top),
                        (x - int(width * 0.07), horizon - int(height * 0.02)),
                        (x + int(width * 0.07), horizon - int(height * 0.02)),
                    ],
                    fill=(*accent_color, 145),
                )
            return

        draw.polygon(
            [(0, horizon), (int(width * 0.22), int(height * 0.42)), (int(width * 0.48), horizon)],
            fill=(15, 23, 42, 150),
        )
        draw.polygon(
            [
                (int(width * 0.32), horizon),
                (int(width * 0.58), int(height * 0.38)),
                (width, horizon),
            ],
            fill=(15, 23, 42, 130),
        )
        draw.rectangle((0, horizon, width, height), fill=(15, 23, 42, 105))

    def _draw_storyboard_subject(
        self,
        draw: Any,
        prompt_text: str,
        width: int,
        height: int,
        accent_color: tuple[int, int, int],
        glow_color: tuple[int, int, int],
    ) -> None:
        """Draw keyword-based scene motifs."""
        lowered_prompt = prompt_text.lower()
        if any(
            self._prompt_has_keyword(lowered_prompt, term)
            for term in ("princess", "castle", "kingdom")
        ):
            self._draw_castle_scene(draw, width, height, accent_color, glow_color)
            return

        if any(
            self._prompt_has_keyword(lowered_prompt, term)
            for term in ("forest", "tree", "woods", "jungle")
        ):
            self._draw_forest_scene(draw, width, height, accent_color, glow_color)
            return

        if any(
            self._prompt_has_keyword(lowered_prompt, term)
            for term in ("robot", "machine", "future")
        ):
            self._draw_robot_scene(draw, width, height, accent_color, glow_color)
            return

        if self._prompt_has_keyword(lowered_prompt, "dragon"):
            self._draw_dragon_scene(draw, width, height, accent_color, glow_color)
            return

        self._draw_character_scene(draw, width, height, accent_color, glow_color)

    def _draw_castle_scene(
        self,
        draw: Any,
        width: int,
        height: int,
        accent_color: tuple[int, int, int],
        glow_color: tuple[int, int, int],
    ) -> None:
        """Draw a castle and central character silhouette."""
        base_y = int(height * 0.72)
        castle_color = (*glow_color, 210)
        shadow_color = (15, 23, 42, 230)
        tower_width = int(width * 0.13)
        center_x = width // 2

        for offset in (-int(width * 0.24), 0, int(width * 0.24)):
            x = center_x + offset
            draw.rectangle(
                (x - tower_width // 2, int(height * 0.36), x + tower_width // 2, base_y),
                fill=shadow_color,
                outline=castle_color,
                width=3,
            )
            draw.polygon(
                [
                    (x - tower_width // 2, int(height * 0.36)),
                    (x, int(height * 0.23)),
                    (x + tower_width // 2, int(height * 0.36)),
                ],
                fill=(*accent_color, 220),
                outline=castle_color,
            )

        draw.rectangle(
            (int(width * 0.23), int(height * 0.49), int(width * 0.77), base_y),
            fill=shadow_color,
            outline=castle_color,
            width=3,
        )
        draw.ellipse(
            (int(width * 0.43), int(height * 0.47), int(width * 0.57), int(height * 0.61)),
            fill=(*glow_color, 235),
        )
        draw.polygon(
            [
                (int(width * 0.5), int(height * 0.58)),
                (int(width * 0.39), int(height * 0.82)),
                (int(width * 0.61), int(height * 0.82)),
            ],
            fill=(*accent_color, 230),
        )

    def _draw_forest_scene(
        self,
        draw: Any,
        width: int,
        height: int,
        accent_color: tuple[int, int, int],
        glow_color: tuple[int, int, int],
    ) -> None:
        """Draw a magical forest composition."""
        ground_y = int(height * 0.76)
        for index, x in enumerate(range(int(width * 0.08), width, max(38, width // 7))):
            tree_height = int(height * (0.3 + (index % 3) * 0.06))
            trunk_width = max(8, width // 55)
            draw.rectangle(
                (x - trunk_width, ground_y - tree_height, x + trunk_width, ground_y),
                fill=(64, 35, 20, 220),
            )
            draw.polygon(
                [
                    (x, ground_y - tree_height - int(height * 0.16)),
                    (x - int(width * 0.08), ground_y - int(height * 0.08)),
                    (x + int(width * 0.08), ground_y - int(height * 0.08)),
                ],
                fill=(*accent_color, 190),
            )

        for index in range(8):
            x = int(width * (0.16 + index * 0.09))
            y = int(height * (0.25 + (index % 4) * 0.08))
            draw.ellipse((x, y, x + 8, y + 8), fill=(*glow_color, 210))

    def _draw_robot_scene(
        self,
        draw: Any,
        width: int,
        height: int,
        accent_color: tuple[int, int, int],
        glow_color: tuple[int, int, int],
    ) -> None:
        """Draw a friendly robot motif."""
        body = (
            int(width * 0.34),
            int(height * 0.42),
            int(width * 0.66),
            int(height * 0.77),
        )
        head = (
            int(width * 0.38),
            int(height * 0.25),
            int(width * 0.62),
            int(height * 0.45),
        )
        draw.rounded_rectangle(body, radius=18, fill=(15, 23, 42, 230), outline=(*glow_color, 230), width=4)
        draw.rounded_rectangle(head, radius=16, fill=(*accent_color, 220), outline=(*glow_color, 230), width=4)
        draw.ellipse((int(width * 0.43), int(height * 0.32), int(width * 0.47), int(height * 0.36)), fill=(*glow_color, 255))
        draw.ellipse((int(width * 0.53), int(height * 0.32), int(width * 0.57), int(height * 0.36)), fill=(*glow_color, 255))
        for index in range(5):
            x = int(width * (0.25 + index * 0.12))
            draw.line((x, int(height * 0.2), x, int(height * 0.86)), fill=(*glow_color, 80), width=2)

    def _draw_dragon_scene(
        self,
        draw: Any,
        width: int,
        height: int,
        accent_color: tuple[int, int, int],
        glow_color: tuple[int, int, int],
    ) -> None:
        """Draw a dragon-like silhouette."""
        body_box = (
            int(width * 0.26),
            int(height * 0.48),
            int(width * 0.74),
            int(height * 0.76),
        )
        draw.ellipse(body_box, fill=(*accent_color, 215), outline=(*glow_color, 230), width=4)
        draw.polygon(
            [
                (int(width * 0.38), int(height * 0.52)),
                (int(width * 0.18), int(height * 0.3)),
                (int(width * 0.48), int(height * 0.42)),
            ],
            fill=(*glow_color, 145),
        )
        draw.polygon(
            [
                (int(width * 0.62), int(height * 0.52)),
                (int(width * 0.82), int(height * 0.3)),
                (int(width * 0.52), int(height * 0.42)),
            ],
            fill=(*glow_color, 145),
        )
        draw.ellipse(
            (int(width * 0.64), int(height * 0.38), int(width * 0.79), int(height * 0.52)),
            fill=(*accent_color, 240),
            outline=(*glow_color, 230),
            width=3,
        )

    def _draw_character_scene(
        self,
        draw: Any,
        width: int,
        height: int,
        accent_color: tuple[int, int, int],
        glow_color: tuple[int, int, int],
    ) -> None:
        """Draw a generic cinematic character scene."""
        center_x = width // 2
        draw.ellipse(
            (center_x - int(width * 0.08), int(height * 0.32), center_x + int(width * 0.08), int(height * 0.48)),
            fill=(*glow_color, 230),
        )
        draw.polygon(
            [
                (center_x, int(height * 0.47)),
                (center_x - int(width * 0.16), int(height * 0.82)),
                (center_x + int(width * 0.16), int(height * 0.82)),
            ],
            fill=(*accent_color, 225),
        )
        draw.ellipse(
            (center_x - int(width * 0.24), int(height * 0.22), center_x + int(width * 0.24), int(height * 0.86)),
            outline=(*glow_color, 115),
            width=4,
        )

    def _draw_storyboard_frame(
        self,
        draw: Any,
        width: int,
        height: int,
        scene: int,
        glow_color: tuple[int, int, int],
    ) -> None:
        """Draw a polished frame and scene marker."""
        margin = max(12, width // 36)
        draw.rounded_rectangle(
            (margin, margin, width - margin, height - margin),
            radius=14,
            outline=(*glow_color, 170),
            width=3,
        )
        marker_size = max(34, width // 12)
        draw.ellipse(
            (margin * 2, margin * 2, margin * 2 + marker_size, margin * 2 + marker_size),
            fill=(15, 23, 42, 185),
            outline=(*glow_color, 180),
            width=2,
        )
        font = self._load_storyboard_font(max(14, marker_size // 3), bold=True)
        draw.text(
            (margin * 2 + marker_size * 0.32, margin * 2 + marker_size * 0.23),
            str(scene),
            fill=(*glow_color, 255),
            font=font,
        )

    def _draw_storyboard_caption(
        self,
        draw: Any,
        prompt_text: str,
        width: int,
        height: int,
    ) -> None:
        """Draw a short unobtrusive caption from the scene prompt."""
        caption = self._storyboard_caption_text(prompt_text)
        if not caption:
            return

        font = self._load_storyboard_font(max(12, width // 40), bold=False)
        panel_height = int(height * 0.16)
        panel_top = height - panel_height - max(12, height // 36)
        draw.rounded_rectangle(
            (max(12, width // 36), panel_top, width - max(12, width // 36), height - max(12, height // 36)),
            radius=12,
            fill=(2, 6, 23, 150),
        )
        lines = self._wrap_placeholder_text(caption, max_chars=max(28, width // 15))[:3]
        for index, line in enumerate(lines):
            draw.text(
                (max(22, width // 28), panel_top + 12 + index * max(15, width // 34)),
                line,
                fill=(248, 250, 252, 230),
                font=font,
            )

    def _storyboard_caption_text(self, prompt_text: str) -> str:
        """Extract the scene instruction from a generated prompt."""
        marker = "Scene must clearly show:"
        if marker in prompt_text:
            caption = prompt_text.split(marker, 1)[1].split(",", 1)[0].strip()
            return self._truncate_error_message(caption, max_length=120)

        return self._truncate_error_message(prompt_text, max_length=120)

    def _load_storyboard_font(
        self,
        size: int,
        bold: bool = False,
    ) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        """Load a common font for local storyboard panels."""
        try:
            from PIL import ImageFont
        except ImportError:
            raise

        candidates = (
            ("arialbd.ttf", "DejaVuSans-Bold.ttf")
            if bold
            else ("arial.ttf", "DejaVuSans.ttf")
        )
        for font_name in candidates:
            try:
                return ImageFont.truetype(font_name, size)
            except OSError:
                continue

        return ImageFont.load_default()

    def _coerce_prompt(self, prompt_item: Prompt | dict[str, Any]) -> tuple[str, int]:
        """Read prompt text and scene number from supported prompt objects."""
        if isinstance(prompt_item, Prompt):
            return prompt_item.prompt, prompt_item.scene

        if isinstance(prompt_item, dict):
            return str(prompt_item.get("prompt", "")), int(prompt_item.get("scene", 0))

        raise InvalidPromptError("Prompt item must be a Prompt model or dictionary.")

    def _failed_responses_for_remaining_prompts(
        self,
        prompt_items: list[Prompt | dict[str, Any]],
        start_index: int,
        error: Exception,
        save_placeholder: bool = True,
    ) -> list[ImageResponse]:
        """Build failure records for prompts skipped after a model-level failure."""
        failed_images: list[ImageResponse] = []

        for fallback_scene, prompt_item in enumerate(
            prompt_items[start_index:],
            start=start_index + 1,
        ):
            try:
                _, scene_number = self._coerce_prompt(prompt_item)
            except Exception:
                scene_number = fallback_scene

            failed_images.append(
                self._failed_response(
                    scene_number,
                    error,
                    save_placeholder=save_placeholder,
                )
            )

        return failed_images

    def _failed_response(
        self,
        scene_number: int,
        error: Exception | str,
        save_placeholder: bool = True,
    ) -> ImageResponse:
        """Return a scene-level image failure with a user-safe error message."""
        try:
            scene = self._validate_scene_number(scene_number)
        except InvalidPromptError:
            scene = 1

        target_path = self._build_image_path(scene=scene)
        error_message = self._build_user_error_message(
            error,
            fallback=f"Image generation failed for scene {scene}.",
        )
        image_path = None

        logger.info(
            "Image generation failed for scene %s: status=failed path=%s error=%s",
            scene,
            target_path.as_posix(),
            error_message,
        )

        if save_placeholder:
            image_path = self.save_placeholder_image(
                scene_number=scene,
                error_message=error_message,
                target_path=target_path,
            )

        return ImageResponse(
            scene=scene,
            status="failed",
            image_path=image_path,
            image_url=None,
            provider="placeholder" if image_path else None,
            warning=None,
            error=error_message,
        )

    def _build_user_error_message(
        self,
        error: Exception | str,
        fallback: str = "Image generation failed.",
    ) -> str:
        """Convert tracebacks and provider payloads into concise UI text."""
        raw_message = str(error).strip()
        if not raw_message:
            return fallback

        message = self._extract_exception_message(raw_message)
        lowered = message.lower()

        if "pollinations" in lowered and "http 524" in lowered:
            return (
                "Pollinations timed out while generating the image. "
                "Try again or lower the image quality/size."
            )

        if "status 524" in lowered or "error code: 524" in lowered:
            return (
                "Image generation timed out upstream. "
                "Try again or lower the image quality/size."
            )

        if "remote end closed connection" in lowered:
            return (
                "The image provider closed the connection before returning an image. "
                "Try again in a moment."
            )

        if (
            "403 forbidden" in lowered
            and (
                "inference providers" in lowered
                or "sufficient permissions" in lowered
                or "huggingface" in lowered
            )
        ):
            return (
                "Hugging Face token lacks permission to call Inference Providers. "
                "Create a token with Inference Providers access or switch image provider."
            )

        if "huggingface.co/docs/huggingface_hub/authentication" in lowered:
            return (
                "Hugging Face authentication failed. Check HF_TOKEN, or use the "
                "Pollinations fallback provider."
            )

        if "invalid username or password" in lowered or "401" in lowered:
            return (
                "Hugging Face authentication failed. Check HF_TOKEN, or use the "
                "Pollinations fallback provider."
            )

        if "hf_token" in lowered or "hugging face" in lowered and "token" in lowered:
            return "HF_TOKEN is required for Hugging Face image generation."

        if "pollinations" in lowered and "http 502" in lowered:
            return (
                "Pollinations image backend is temporarily unavailable (HTTP 502). "
                "Try again later or use a different image provider."
            )

        if "exhausted balance" in lowered and "fal" in lowered:
            return (
                "fal.ai account balance is exhausted. Top up fal.ai billing or "
                "use a different image provider."
            )

        if "user is locked" in lowered and "exhausted balance" in lowered:
            return (
                "fal.ai account balance is exhausted. Top up fal.ai billing or "
                "use a different image provider."
            )

        if "bad_gateway" in lowered or "bad gateway" in lowered:
            return (
                "Image provider backend is temporarily unavailable (HTTP 502). "
                "Try again later or use a different image provider."
            )

        return self._truncate_error_message(message)

    def _extract_exception_message(self, raw_message: str) -> str:
        """Return the final exception line from a traceback-like string."""
        lines = [line.strip() for line in raw_message.splitlines() if line.strip()]
        if not lines:
            return raw_message

        message = lines[-1]
        if "Traceback (most recent call last)" in raw_message:
            for line in reversed(lines):
                if line.startswith(("File ", "^", "Traceback ")):
                    continue
                if line.startswith(("During handling", "The above exception")):
                    continue
                message = line
                break

        prefix, separator, detail = message.partition(": ")
        if separator and ("." in prefix or prefix.endswith("Error")):
            message = detail

        return self._truncate_provider_payload(message)

    def _truncate_provider_payload(self, message: str) -> str:
        """Remove long structured provider response bodies from error text."""
        for marker in (": {", ": [", "\n{", "\n["):
            marker_index = message.find(marker)
            if marker_index != -1:
                return message[:marker_index].rstrip(".: ") + "."

        return message

    def _truncate_error_message(self, message: str, max_length: int = 240) -> str:
        """Keep stored UI error messages short enough for cards and history."""
        if len(message) <= max_length:
            return message

        return f"{message[: max_length - 1].rstrip()}..."

    def _save_placeholder_image(
        self,
        target_path: Path,
        scene_number: int,
        error_message: str,
    ) -> bool:
        """Save a simple placeholder PNG for a failed scene."""
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            logger.exception(
                "Unable to save placeholder for scene %s because Pillow is unavailable",
                scene_number,
            )
            return False

        logger.info(
            "Saving placeholder image for failed scene %s: path=%s",
            scene_number,
            target_path.as_posix(),
        )

        try:
            image = Image.new(
                "RGB",
                (self.image_width, self.image_height),
                color=(15, 23, 42),
            )
            draw = ImageDraw.Draw(image)
            font = ImageFont.load_default()
            margin = 16
            line_height = 16
            lines = [
                f"Scene {scene_number}",
                "Image generation failed",
                *self._wrap_placeholder_text(error_message, max_chars=30)[:5],
            ]

            for line_index, line in enumerate(lines):
                fill = (248, 250, 252) if line_index == 0 else (254, 202, 202)
                draw.text(
                    (margin, margin + (line_index * line_height)),
                    line,
                    fill=fill,
                    font=font,
                )

            self._save_image(
                image=image,
                target_path=target_path,
                scene_number=scene_number,
            )
        except Exception:
            logger.exception(
                "Placeholder image save failed for scene %s: path=%s",
                scene_number,
                target_path.as_posix(),
            )
            return False

        logger.info(
            "Placeholder image saved for failed scene %s: path=%s",
            scene_number,
            target_path.as_posix(),
        )
        return True

    def _wrap_placeholder_text(self, text: str, max_chars: int) -> list[str]:
        """Wrap placeholder text without adding a text layout dependency."""
        words = text.split()
        if not words:
            return []

        lines: list[str] = []
        current_line = ""

        for word in words:
            candidate = f"{current_line} {word}".strip()
            if len(candidate) <= max_chars:
                current_line = candidate
                continue

            if current_line:
                lines.append(current_line)
            current_line = word[:max_chars]

        if current_line:
            lines.append(current_line)

        return lines

    def _validate_prompt(self, prompt: str) -> str:
        """Validate and normalize an image prompt."""
        if not isinstance(prompt, str):
            raise InvalidPromptError("Prompt must be a string.")

        prompt_text = prompt.strip()
        if not prompt_text:
            raise InvalidPromptError("Prompt cannot be empty.")

        return prompt_text

    def _validate_scene_number(self, scene_number: int) -> int:
        """Validate scene numbering before building the output file path."""
        try:
            scene = int(scene_number)
        except (TypeError, ValueError) as exc:
            raise InvalidPromptError("Scene number must be an integer.") from exc

        if scene < 1:
            raise InvalidPromptError("Scene number must be greater than zero.")

        return scene

    def _build_image_path(self, scene: int) -> Path:
        """Build the required browser-served image path for a generated scene."""
        return self.output_dir / f"scene_{scene}.png"

    def _normalize_provider(self, provider: str) -> str:
        """Normalize configured image provider aliases."""
        normalized = provider.strip().lower().replace("_", "-")
        if normalized in {"pollinations", "pollination", "pollinations-ai"}:
            return "pollinations"

        if normalized in {"fal", "flux", "fal-flux", "fal-ai"}:
            return "fal"

        if normalized in {
            "hf",
            "hf-inference",
            "hugging-face",
            "huggingface",
            "huggingface-hub",
        }:
            return "huggingface"

        if normalized in {"storyboard", "storybook", "local-storyboard", "local-art"}:
            return "storyboard"

        if normalized in {"stable", "stable-diffusion", "sd", "local"}:
            return "stable-diffusion"

        raise ValueError(
            "CINEGEN_IMAGE_PROVIDER must be 'pollinations', 'huggingface', 'fal', "
            "'storyboard', or 'stable-diffusion'."
        )

    def _parse_provider_list(self, raw_provider_list: str) -> list[str]:
        """Parse a comma-separated provider list, skipping invalid names."""
        providers: list[str] = []
        for provider in raw_provider_list.split(","):
            provider_name = provider.strip()
            if not provider_name:
                continue

            try:
                normalized_provider = self._normalize_provider(provider_name)
            except ValueError:
                logger.warning("Ignoring invalid fallback image provider: %s", provider)
                continue

            if normalized_provider == "stable-diffusion":
                logger.warning(
                    "Ignoring local Stable Diffusion as a hosted image fallback"
                )
                continue

            if normalized_provider not in providers:
                providers.append(normalized_provider)

        return providers

    def _env_bool(self, name: str, default: bool) -> bool:
        """Read a boolean environment variable."""
        raw_value = os.getenv(name)
        if raw_value is None:
            return default

        return raw_value.strip().lower() in {"1", "true", "yes", "on"}

    def _env_int(self, name: str, default: int) -> int:
        """Read an integer environment variable with a safe fallback."""
        raw_value = os.getenv(name)
        if raw_value is None:
            return default

        try:
            return int(raw_value)
        except ValueError:
            logger.warning(
                "Invalid integer env var %s=%r; using %s",
                name,
                raw_value,
                default,
            )
            return default

    def _env_float(self, name: str, default: float) -> float:
        """Read a float environment variable with a safe fallback."""
        raw_value = os.getenv(name)
        if raw_value is None:
            return default

        try:
            return float(raw_value)
        except ValueError:
            logger.warning(
                "Invalid float env var %s=%r; using %s",
                name,
                raw_value,
                default,
            )
            return default

    def _require_torch(self) -> Any:
        """Return the loaded torch module or fail with a service error."""
        if self._torch is None:
            raise ModelLoadError("Torch was not initialized with the image model.")

        return self._torch

    def _release_cuda_memory(self) -> None:
        """Release cached CUDA memory after each generation when using a GPU."""
        if self.device == "cuda" and self._torch is not None:
            self._torch.cuda.empty_cache()
