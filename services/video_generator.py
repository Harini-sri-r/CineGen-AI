"""Cinematic MP4 generation for CineGen AI."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import traceback
from types import SimpleNamespace
from typing import Any, Iterable

from PIL import Image, ImageDraw, ImageFont

from models.story import AudioResponse, ImageResponse, Scene
from utils.logger import get_logger

logger = get_logger(__name__)


class VideoGenerationError(RuntimeError):
    """Raised when MoviePy cannot render a video."""


@dataclass
class VideoRenderResult:
    """Rendered video metadata."""

    video_path: str
    duration_seconds: float


@dataclass
class SceneClipInput:
    """Resolved scene media used by MoviePy."""

    scene: int
    description: str
    image_path: Path
    audio_path: Path | None
    duration_seconds: float


class VideoGenerator:
    """Create a narrated cinematic MP4 from generated images and audio."""

    def __init__(
        self,
        output_dir: str | Path = "outputs/videos",
        output_root: str | Path = "outputs",
        music_dir: str | Path = "assets/music",
        resolution: tuple[int, int] = (1280, 720),
        fps: int | None = None,
        default_scene_duration: float | None = None,
        transition_seconds: float | None = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.output_root = Path(output_root)
        self.music_dir = Path(music_dir)
        self.resolution = resolution
        self.fps = fps or self._env_int("CINEGEN_VIDEO_FPS", 24)
        self.default_scene_duration = default_scene_duration or self._env_float(
            "CINEGEN_DEFAULT_SCENE_DURATION_SECONDS",
            4.0,
        )
        self.transition_seconds = transition_seconds or self._env_float(
            "CINEGEN_VIDEO_TRANSITION_SECONDS",
            0.45,
        )
        self.title_duration = self._env_float("CINEGEN_VIDEO_TITLE_SECONDS", 2.5)
        self.credits_duration = self._env_float("CINEGEN_VIDEO_CREDITS_SECONDS", 2.5)
        self.ken_burns_zoom = self._env_float("CINEGEN_VIDEO_KEN_BURNS_ZOOM", 0.06)
        self.music_volume = self._env_float("CINEGEN_BACKGROUND_MUSIC_VOLUME", 0.1)

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.music_dir.mkdir(parents=True, exist_ok=True)

    def create_video(
        self,
        scenes: Iterable[Scene],
        images: Iterable[ImageResponse],
        audio: Iterable[AudioResponse],
        output_name: str | None = None,
        target_duration_seconds: float | None = None,
    ) -> VideoRenderResult:
        """Create an MP4 from scene images and narration audio."""
        scene_items = self._build_scene_inputs(
            scenes=list(scenes),
            images=list(images),
            audio=list(audio),
        )
        if not scene_items:
            raise VideoGenerationError("No scenes were available for video rendering.")

        scene_items = self._fit_scene_durations_to_target(
            scene_items,
            target_duration_seconds=target_duration_seconds,
        )
        target_path = self._build_video_path(output_name)
        try:
            duration_seconds = self._write_video_with_moviepy(
                scene_items=scene_items,
                target_path=target_path,
            )
        except Exception as exc:
            error_trace = traceback.format_exc()
            logger.exception("Video generation failed")
            logger.exception(error_trace)
            raise VideoGenerationError(error_trace) from exc

        return VideoRenderResult(
            video_path=target_path.as_posix(),
            duration_seconds=duration_seconds,
        )

    def _build_scene_inputs(
        self,
        scenes: list[Scene],
        images: list[ImageResponse],
        audio: list[AudioResponse],
    ) -> list[SceneClipInput]:
        """Resolve scene media paths and durations."""
        images_by_scene = {image.scene: image for image in images}
        audio_by_scene = {audio_item.scene: audio_item for audio_item in audio}
        scene_items: list[SceneClipInput] = []

        for scene in scenes:
            image = images_by_scene.get(scene.scene)
            audio_item = audio_by_scene.get(scene.scene)
            image_path = self._resolve_image_path(scene=scene, image=image)
            audio_path = self._resolve_audio_path(audio_item)
            duration_seconds = self._duration_for_scene(audio_item)

            scene_items.append(
                SceneClipInput(
                    scene=scene.scene,
                    description=scene.description,
                    image_path=image_path,
                    audio_path=audio_path,
                    duration_seconds=duration_seconds,
                )
            )

        return scene_items

    def _write_video_with_moviepy(
        self,
        scene_items: list[SceneClipInput],
        target_path: Path,
    ) -> float:
        """Render the video using MoviePy."""
        moviepy = self._load_moviepy()
        clips: list[Any] = []
        closeables: list[Any] = []

        with TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            title_image = self._create_text_frame(
                temp_dir / "title.png",
                "CineGen AI",
                "Story-to-video generation",
            )
            credits_image = self._create_text_frame(
                temp_dir / "credits.png",
                "Generated using CineGen AI",
                "Thank you for watching",
            )

            clips.append(
                self._with_fades(
                    moviepy.ImageClip(str(title_image)).set_duration(self.title_duration),
                    moviepy,
                )
            )

            for index, scene_item in enumerate(scene_items):
                clip = self._create_scene_clip(moviepy, scene_item)
                if index > 0 and hasattr(clip, "crossfadein"):
                    clip = clip.crossfadein(
                        min(self.transition_seconds, scene_item.duration_seconds / 3)
                    )
                clips.append(clip)

            clips.append(
                self._with_fades(
                    moviepy.ImageClip(str(credits_image)).set_duration(
                        self.credits_duration
                    ),
                    moviepy,
                )
            )

            final_clip = moviepy.concatenate_videoclips(
                clips,
                method="compose",
                padding=-self.transition_seconds,
            )
            final_clip = self._apply_background_music(moviepy, final_clip, closeables)
            duration_seconds = float(final_clip.duration or 0)

            target_path.parent.mkdir(parents=True, exist_ok=True)
            final_clip.write_videofile(
                str(target_path),
                fps=self.fps,
                codec="libx264",
                audio=final_clip.audio is not None,
                audio_codec="aac",
                preset="medium",
                temp_audiofile=str(temp_dir / "cinegen-temp-audio.m4a"),
                remove_temp=True,
                logger=None,
            )

            closeables.append(final_clip)

        for clip in [*clips, *closeables]:
            close = getattr(clip, "close", None)
            if callable(close):
                close()

        return duration_seconds

    def _create_scene_clip(self, moviepy: SimpleNamespace, scene_item: SceneClipInput) -> Any:
        """Create a Ken Burns image clip with optional narration audio."""
        with Image.open(scene_item.image_path) as image:
            image_width, image_height = image.size

        target_width, target_height = self.resolution
        base_scale = max(target_width / image_width, target_height / image_height)
        duration = scene_item.duration_seconds
        image_clip = moviepy.ImageClip(str(scene_item.image_path)).set_duration(duration)
        zooming_clip = image_clip.resize(
            lambda t: base_scale * (1 + self.ken_burns_zoom * (t / max(duration, 0.1)))
        )
        zooming_clip = zooming_clip.set_position(("center", "center"))
        clip = moviepy.CompositeVideoClip(
            [zooming_clip],
            size=self.resolution,
            bg_color=(0, 0, 0),
        ).set_duration(duration)

        if scene_item.audio_path:
            audio_clip = moviepy.AudioFileClip(str(scene_item.audio_path))
            audio_duration = float(getattr(audio_clip, "duration", 0) or 0)
            if audio_duration > duration and hasattr(audio_clip, "subclip"):
                audio_clip = audio_clip.subclip(0, duration)
            clip = clip.set_audio(audio_clip)

        return self._with_fades(clip, moviepy, duration)

    def _fit_scene_durations_to_target(
        self,
        scene_items: list[SceneClipInput],
        target_duration_seconds: float | None,
    ) -> list[SceneClipInput]:
        """Scale scene durations so the final video lands near the target."""
        if target_duration_seconds is None or target_duration_seconds <= 0:
            return scene_items

        transition_overlap = self.transition_seconds * (len(scene_items) + 1)
        fixed_duration = self.title_duration + self.credits_duration
        target_scene_total = (
            float(target_duration_seconds) - fixed_duration + transition_overlap
        )
        if target_scene_total <= 0:
            target_scene_total = max(1.0, float(target_duration_seconds) * 0.75)

        minimum_scene_duration = min(1.0, target_scene_total / len(scene_items))
        base_durations = [
            max(minimum_scene_duration, item.duration_seconds) for item in scene_items
        ]
        scaled_durations = self._scale_durations(
            base_durations,
            target_total=target_scene_total,
            minimum_duration=minimum_scene_duration,
        )

        return [
            SceneClipInput(
                scene=item.scene,
                description=item.description,
                image_path=item.image_path,
                audio_path=item.audio_path,
                duration_seconds=duration,
            )
            for item, duration in zip(scene_items, scaled_durations, strict=True)
        ]

    def _scale_durations(
        self,
        durations: list[float],
        target_total: float,
        minimum_duration: float,
    ) -> list[float]:
        """Scale durations proportionally, preserving a minimum per scene."""
        if not durations:
            return []

        base_total = sum(durations)
        if base_total <= 0:
            return [target_total / len(durations)] * len(durations)

        scale = target_total / base_total
        scaled = [max(minimum_duration, duration * scale) for duration in durations]
        delta = target_total - sum(scaled)

        for index in range(len(scaled) - 1, -1, -1):
            if abs(delta) < 0.001:
                break

            if delta > 0:
                scaled[index] += delta
                break

            removable = scaled[index] - minimum_duration
            adjustment = min(removable, abs(delta))
            scaled[index] -= adjustment
            delta += adjustment

        return scaled

    def _with_fades(
        self,
        clip: Any,
        moviepy: SimpleNamespace,
        duration: float | None = None,
    ) -> Any:
        """Apply subtle fade in/out effects to a clip."""
        clip_duration = duration or float(getattr(clip, "duration", 0) or 0)
        fade_duration = min(0.45, max(0.1, clip_duration / 4))
        return clip.fx(moviepy.vfx.fadein, fade_duration).fx(
            moviepy.vfx.fadeout,
            fade_duration,
        )

    def _apply_background_music(
        self,
        moviepy: SimpleNamespace,
        final_clip: Any,
        closeables: list[Any],
    ) -> Any:
        """Mix optional background music at low volume under narration."""
        background_path = self.music_dir / "background.mp3"
        if not background_path.exists():
            return final_clip

        background_clip = moviepy.AudioFileClip(str(background_path))
        closeables.append(background_clip)
        background_clip = moviepy.afx.audio_loop(
            background_clip,
            duration=final_clip.duration,
        ).volumex(self.music_volume)

        if final_clip.audio is None:
            return final_clip.set_audio(background_clip)

        return final_clip.set_audio(
            moviepy.CompositeAudioClip([final_clip.audio, background_clip])
        )

    def _load_moviepy(self) -> SimpleNamespace:
        """Load MoviePy symbols lazily."""
        if not hasattr(Image, "ANTIALIAS"):
            Image.ANTIALIAS = Image.Resampling.LANCZOS

        try:
            from moviepy.editor import (
                AudioFileClip,
                CompositeAudioClip,
                CompositeVideoClip,
                ImageClip,
                concatenate_videoclips,
                vfx,
            )
            from moviepy.audio.fx import all as afx
        except ImportError as exc:
            raise VideoGenerationError(
                "MoviePy is not installed. Run: pip install -r requirements.txt"
            ) from exc

        return SimpleNamespace(
            AudioFileClip=AudioFileClip,
            CompositeAudioClip=CompositeAudioClip,
            CompositeVideoClip=CompositeVideoClip,
            ImageClip=ImageClip,
            concatenate_videoclips=concatenate_videoclips,
            vfx=vfx,
            afx=afx,
        )

    def _resolve_image_path(self, scene: Scene, image: ImageResponse | None) -> Path:
        """Resolve a scene image or create a placeholder if needed."""
        if image and image.image_path:
            resolved_path = self._resolve_output_path(image.image_path)
            if resolved_path and resolved_path.exists():
                return resolved_path

        return self._create_video_placeholder(scene)

    def _resolve_audio_path(self, audio_item: AudioResponse | None) -> Path | None:
        """Resolve a narration path when generation succeeded."""
        if not audio_item or audio_item.status != "success" or not audio_item.audio_path:
            return None

        resolved_path = self._resolve_output_path(audio_item.audio_path)
        if resolved_path and resolved_path.exists():
            return resolved_path

        return None

    def _duration_for_scene(self, audio_item: AudioResponse | None) -> float:
        """Use narration duration when available, otherwise a readable fallback."""
        if audio_item and audio_item.duration_seconds and audio_item.duration_seconds > 0:
            return max(1.0, float(audio_item.duration_seconds))

        return self.default_scene_duration

    def _resolve_output_path(self, stored_path: str) -> Path | None:
        """Resolve a stored media path under the configured output root."""
        normalized_path = Path(stored_path.replace("\\", "/"))
        if normalized_path.is_absolute() or ".." in normalized_path.parts:
            logger.warning("Rejected unsafe media path: %s", stored_path)
            return None

        path_parts = normalized_path.parts
        if path_parts and path_parts[0] in {self.output_root.name, "outputs"}:
            return self.output_root.joinpath(*path_parts[1:])

        return self.output_root / normalized_path

    def _create_video_placeholder(self, scene: Scene) -> Path:
        """Create a placeholder image for missing scene media."""
        placeholder_path = self.output_root / "images" / f"video_scene_{scene.scene}.png"
        placeholder_path.parent.mkdir(parents=True, exist_ok=True)
        return self._create_text_frame(
            placeholder_path,
            f"Scene {scene.scene}",
            "Image unavailable",
        )

    def _create_text_frame(self, target_path: Path, title: str, subtitle: str) -> Path:
        """Create a simple 1280x720 PNG text frame."""
        width, height = self.resolution
        image = Image.new("RGB", self.resolution, color=(15, 23, 42))
        draw = ImageDraw.Draw(image)
        title_font = self._load_font(72)
        subtitle_font = self._load_font(34)

        title_bbox = draw.textbbox((0, 0), title, font=title_font)
        subtitle_bbox = draw.textbbox((0, 0), subtitle, font=subtitle_font)
        title_width = title_bbox[2] - title_bbox[0]
        title_height = title_bbox[3] - title_bbox[1]
        subtitle_width = subtitle_bbox[2] - subtitle_bbox[0]

        draw.text(
            ((width - title_width) / 2, (height - title_height) / 2 - 42),
            title,
            fill=(248, 250, 252),
            font=title_font,
        )
        draw.text(
            ((width - subtitle_width) / 2, height / 2 + 48),
            subtitle,
            fill=(191, 219, 254),
            font=subtitle_font,
        )

        target_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(target_path, format="PNG")
        return target_path

    def _load_font(self, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        """Load a common system font with a default fallback."""
        for font_name in ("arial.ttf", "DejaVuSans.ttf"):
            try:
                return ImageFont.truetype(font_name, size)
            except OSError:
                continue

        return ImageFont.load_default()

    def _build_video_path(self, output_name: str | None) -> Path:
        """Build the MP4 output path."""
        if output_name:
            safe_name = Path(output_name).name
            if not safe_name.lower().endswith(".mp4"):
                safe_name = f"{Path(safe_name).stem}.mp4"
        else:
            from datetime import datetime

            safe_name = f"story_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"

        return self.output_dir / safe_name

    def _env_int(self, name: str, default: int) -> int:
        """Read an integer environment variable with a safe fallback."""
        raw_value = os.getenv(name)
        if raw_value is None:
            return default

        try:
            return int(raw_value)
        except ValueError:
            logger.warning("Invalid integer env var %s=%r; using %s", name, raw_value, default)
            return default

    def _env_float(self, name: str, default: float) -> float:
        """Read a float environment variable with a safe fallback."""
        raw_value = os.getenv(name)
        if raw_value is None:
            return default

        try:
            return float(raw_value)
        except ValueError:
            logger.warning("Invalid float env var %s=%r; using %s", name, raw_value, default)
            return default
