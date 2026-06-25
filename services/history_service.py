"""History reading service for saved CineGen AI outputs."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
import re
from typing import Any

from pydantic import ValidationError

from models.story import HistoryDetail, HistoryItem, HistoryStats, ImageResponse
from services.image_generator import ImageGenerator
from utils.logger import get_logger

logger = get_logger(__name__)


class HistoryService:
    """Read and validate generated story JSON files from the outputs folder."""

    _file_name_pattern = re.compile(r"^story_(\d{8})_(\d{6})\.json$")
    _created_at_format = "%Y-%m-%d %H:%M:%S"
    _file_timestamp_format = "%Y%m%d%H%M%S"

    def __init__(self, output_dir: str | Path = "outputs") -> None:
        self.output_dir = Path(output_dir)
        self.images_dir = self.output_dir / "images"
        self.placeholder_generator = ImageGenerator(
            output_dir=self.images_dir,
            image_width=256,
            image_height=256,
            num_inference_steps=8,
            guidance_scale=6.0,
        )

    def list_history(self) -> list[HistoryItem]:
        """Return valid saved story files, newest first."""
        logger.info("History list requested from %s", self.output_dir)

        if not self.output_dir.exists():
            logger.info("History output directory does not exist: %s", self.output_dir)
            return []

        items: list[tuple[datetime, HistoryItem]] = []
        for path in self.output_dir.glob("story_*.json"):
            created_at = self._created_at_from_filename(path.name)
            if created_at is None:
                logger.warning("Ignoring history file with invalid name: %s", path.name)
                continue

            if self._read_valid_detail(path) is None:
                continue

            items.append(
                (
                    created_at,
                    HistoryItem(
                        file=path.name,
                        created_at=created_at.strftime(self._created_at_format),
                    ),
                )
            )

        items.sort(key=lambda item: item[0], reverse=True)
        logger.info("History list completed: %s valid files", len(items))
        return [item for _, item in items]

    def get_history_detail(self, filename: str) -> HistoryDetail | None:
        """Return one saved story result, or None when it is missing or invalid."""
        logger.info("History detail requested: %s", filename)

        if not self._is_safe_history_filename(filename):
            logger.warning("Rejected unsafe history filename: %s", filename)
            return None

        target_path = self.output_dir / filename
        if not target_path.exists() or not target_path.is_file():
            logger.info("History file not found: %s", target_path)
            return None

        return self._read_valid_detail(target_path, repair_missing_images=True)

    def get_stats(self) -> HistoryStats:
        """Calculate aggregate counts from valid saved story files."""
        logger.info("History stats requested from %s", self.output_dir)
        total_stories = 0
        total_scenes = 0
        total_images = 0

        if not self.output_dir.exists():
            return HistoryStats(total_stories=0, total_scenes=0, total_images=0)

        for path in self.output_dir.glob("story_*.json"):
            if self._created_at_from_filename(path.name) is None:
                continue

            detail = self._read_valid_detail(path)
            if detail is None:
                continue

            total_stories += 1
            total_scenes += len(detail.scenes)
            total_images += sum(1 for image in detail.images if image.status == "success")

        return HistoryStats(
            total_stories=total_stories,
            total_scenes=total_scenes,
            total_images=total_images,
        )

    def _read_valid_detail(
        self,
        path: Path,
        repair_missing_images: bool = False,
    ) -> HistoryDetail | None:
        """Load and validate a saved output file."""
        try:
            with path.open("r", encoding="utf-8") as file:
                payload: Any = json.load(file)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Ignoring unreadable history file %s: %s", path.name, exc)
            return None

        try:
            detail = HistoryDetail.model_validate(payload)
        except ValidationError as exc:
            logger.warning("Ignoring invalid history file %s: %s", path.name, exc)
            return None

        if repair_missing_images:
            return self._repair_missing_history_images(detail, source_path=path)

        return detail

    def _repair_missing_history_images(
        self,
        detail: HistoryDetail,
        source_path: Path,
    ) -> HistoryDetail:
        """Create placeholders for saved history records whose image files are gone."""
        repaired_images: list[ImageResponse] = []

        for image in detail.images:
            if not image.image_path or image.status == "skipped":
                repaired_images.append(image)
                continue

            resolved_path = self._resolve_output_path(image.image_path)
            if resolved_path is not None and resolved_path.exists():
                repaired_images.append(image)
                continue

            repaired_images.append(
                self._repair_missing_history_image(
                    image=image,
                    resolved_path=resolved_path,
                    source_path=source_path,
                )
            )

        return detail.model_copy(update={"images": repaired_images})

    def _repair_missing_history_image(
        self,
        image: ImageResponse,
        resolved_path: Path | None,
        source_path: Path,
    ) -> ImageResponse:
        """Return a failed image record with a saved placeholder when possible."""
        error_message = (
            "Saved image file was missing; placeholder image generated for history."
        )

        logger.warning(
            "History image missing for %s scene %s: image_path=%s resolved_path=%s",
            source_path.name,
            image.scene,
            image.image_path,
            resolved_path.as_posix() if resolved_path else None,
        )

        if resolved_path is None:
            return image.model_copy(
                update={
                    "status": "failed",
                    "image_path": None,
                    "image_url": None,
                    "error": error_message,
                }
            )

        placeholder_path = self.placeholder_generator.save_placeholder_image(
            scene_number=image.scene,
            error_message=error_message,
            target_path=resolved_path,
        )

        if placeholder_path is None:
            logger.error(
                "Unable to create history placeholder for %s scene %s",
                source_path.name,
                image.scene,
            )
            return image.model_copy(
                update={
                    "status": "failed",
                    "image_path": None,
                    "image_url": None,
                    "error": error_message,
                }
            )

        logger.info(
            "History placeholder saved for %s scene %s: %s",
            source_path.name,
            image.scene,
            placeholder_path,
        )

        return image.model_copy(
            update={
                "status": "failed",
                "image_path": image.image_path,
                "image_url": None,
                "error": error_message,
            }
        )

    def _resolve_output_path(self, image_path: str) -> Path | None:
        """Resolve a stored image path under the configured output directory."""
        normalized_path = Path(image_path.replace("\\", "/"))

        if normalized_path.is_absolute() or ".." in normalized_path.parts:
            logger.warning("Rejected unsafe history image path: %s", image_path)
            return None

        path_parts = normalized_path.parts
        if path_parts and path_parts[0] in {self.output_dir.name, "outputs"}:
            return self.output_dir.joinpath(*path_parts[1:])

        return self.output_dir / normalized_path

    def _is_safe_history_filename(self, filename: str) -> bool:
        """Allow only generated story JSON names, never paths."""
        if Path(filename).name != filename:
            return False

        return self._created_at_from_filename(filename) is not None

    def _created_at_from_filename(self, filename: str) -> datetime | None:
        """Parse the creation timestamp from a generated output filename."""
        match = self._file_name_pattern.match(filename)
        if match is None:
            return None

        timestamp = "".join(match.groups())
        try:
            return datetime.strptime(timestamp, self._file_timestamp_format)
        except ValueError:
            return None
