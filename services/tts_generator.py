"""Text-to-speech narration generation for CineGen AI videos."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
import traceback
from typing import Iterable

from models.story import AudioResponse, Scene
from utils.logger import get_logger

logger = get_logger(__name__)


class TTSGenerationError(RuntimeError):
    """Raised when narration generation cannot be completed."""


class TTSGenerator:
    """Generate one Edge-TTS MP3 narration file per scene."""

    def __init__(
        self,
        output_dir: str | Path = "outputs/audio",
        voice: str | None = None,
        rate: str | None = None,
        volume: str | None = None,
        pitch: str | None = None,
        max_concurrency: int | None = None,
        connect_timeout_seconds: int | None = None,
        receive_timeout_seconds: int | None = None,
        scene_timeout_seconds: float | None = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.voice = voice or os.getenv("CINEGEN_TTS_VOICE", "en-US-GuyNeural")
        self.rate = rate or os.getenv("CINEGEN_TTS_RATE", "+0%")
        self.volume = volume or os.getenv("CINEGEN_TTS_VOLUME", "+0%")
        self.pitch = pitch or os.getenv("CINEGEN_TTS_PITCH", "+0Hz")
        self.max_concurrency = max_concurrency or self._env_int(
            "CINEGEN_TTS_MAX_CONCURRENCY",
            4,
        )
        self.connect_timeout_seconds = connect_timeout_seconds or self._env_int(
            "CINEGEN_TTS_CONNECT_TIMEOUT_SECONDS",
            8,
        )
        self.receive_timeout_seconds = receive_timeout_seconds or self._env_int(
            "CINEGEN_TTS_RECEIVE_TIMEOUT_SECONDS",
            20,
        )
        self.scene_timeout_seconds = scene_timeout_seconds or self._env_float(
            "CINEGEN_TTS_SCENE_TIMEOUT_SECONDS",
            30.0,
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_narrations(self, scenes: Iterable[Scene]) -> list[AudioResponse]:
        """Generate scene narration files in parallel where possible."""
        scene_items = list(scenes)
        if not scene_items:
            return []

        return asyncio.run(self._generate_narrations_async(scene_items))

    async def _generate_narrations_async(
        self,
        scenes: list[Scene],
    ) -> list[AudioResponse]:
        """Generate narration files with bounded async concurrency."""
        semaphore = asyncio.Semaphore(max(1, self.max_concurrency))

        async def generate_one(scene: Scene) -> AudioResponse:
            async with semaphore:
                return await self._generate_scene_narration(scene)

        return await asyncio.gather(*(generate_one(scene) for scene in scenes))

    async def _generate_scene_narration(self, scene: Scene) -> AudioResponse:
        """Generate narration for one scene and return a recoverable result."""
        target_path = self._build_audio_path(scene.scene)
        narration_text = scene.description.strip()

        if not narration_text:
            return AudioResponse(
                scene=scene.scene,
                status="skipped",
                audio_path=None,
                audio_url=None,
                duration_seconds=None,
                error="Scene description was empty; narration skipped.",
            )

        try:
            import edge_tts

            communicate = edge_tts.Communicate(
                narration_text,
                self.voice,
                rate=self.rate,
                volume=self.volume,
                pitch=self.pitch,
                connect_timeout=self.connect_timeout_seconds,
                receive_timeout=self.receive_timeout_seconds,
            )
            await asyncio.wait_for(
                communicate.save(str(target_path)),
                timeout=max(0.01, self.scene_timeout_seconds),
            )
            duration_seconds = self._measure_audio_duration(target_path)
        except asyncio.TimeoutError as exc:
            error = (
                f"Narration generation timed out after "
                f"{self.scene_timeout_seconds:g} seconds."
            )
            logger.exception("Narration generation timed out for scene %s", scene.scene)
            return AudioResponse(
                scene=scene.scene,
                status="failed",
                audio_path=None,
                audio_url=None,
                duration_seconds=None,
                error=error,
            )
        except Exception as exc:
            error_trace = traceback.format_exc()
            logger.exception("Narration generation failed for scene %s", scene.scene)
            logger.exception(error_trace)
            return AudioResponse(
                scene=scene.scene,
                status="failed",
                audio_path=None,
                audio_url=None,
                duration_seconds=None,
                error=str(exc) or error_trace,
            )

        return AudioResponse(
            scene=scene.scene,
            status="success",
            audio_path=target_path.as_posix(),
            audio_url=None,
            duration_seconds=duration_seconds,
            error=None,
        )

    def _measure_audio_duration(self, audio_path: Path) -> float | None:
        """Measure MP3 duration with MoviePy when available."""
        try:
            try:
                from moviepy.editor import AudioFileClip
            except ImportError:
                from moviepy import AudioFileClip

            clip = AudioFileClip(str(audio_path))
            try:
                return float(clip.duration or 0)
            finally:
                clip.close()
        except Exception:
            logger.debug("Unable to measure narration duration: %s", audio_path)
            return None

    def _build_audio_path(self, scene_number: int) -> Path:
        """Build the output path for a scene narration MP3."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        return self.output_dir / f"scene_{scene_number}.mp3"

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
