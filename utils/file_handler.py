"""JSON file storage utilities for CineGen AI."""

import json
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from pydantic import BaseModel

from models.story import ImageResponse, ImageSummary, Prompt, Scene


class FileSaveError(RuntimeError):
    """Raised when story output cannot be saved to disk."""


class FileHandler:
    """Persist story processing results as JSON files."""

    def __init__(self, output_dir: str | Path = "outputs") -> None:
        """Create a file handler for the configured output directory."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_story_result(
        self,
        story: str,
        scenes: list[Scene],
        prompts: list[Prompt],
        images: list[ImageResponse] | None = None,
        image_summary: ImageSummary | None = None,
        status: str | None = None,
        message: str | None = None,
    ) -> str:
        """Save a processed story result and return the JSON file name."""
        file_name = self._build_file_name()
        target_path = self.output_dir / file_name

        payload = {
            "success": True,
            "status": status,
            "message": message,
            "story": story,
            "scenes": self._serialize_models(scenes),
            "prompts": self._serialize_models(prompts),
            "images": self._serialize_models(images or []),
            "image_summary": (
                image_summary.model_dump() if image_summary is not None else None
            ),
        }

        try:
            self._write_json_atomic(target_path, payload)
        except OSError as exc:
            raise FileSaveError(f"Failed to save output file: {target_path}") from exc

        return file_name

    def update_story_image(self, file_name: str, image: ImageResponse) -> None:
        """Update one scene image record in a saved story JSON file."""
        if not self._is_safe_story_file_name(file_name):
            raise FileSaveError(f"Unsafe story output filename: {file_name}")

        target_path = self.output_dir / file_name
        try:
            with target_path.open("r", encoding="utf-8") as story_file:
                payload: dict[str, Any] = json.load(story_file)
        except (OSError, json.JSONDecodeError) as exc:
            raise FileSaveError(f"Failed to read output file: {target_path}") from exc

        images = [
            ImageResponse.model_validate(item)
            for item in payload.get("images", [])
            if isinstance(item, dict)
        ]
        updated_images: list[ImageResponse] = []
        replaced = False

        for existing_image in images:
            if existing_image.scene == image.scene:
                updated_images.append(image)
                replaced = True
            else:
                updated_images.append(existing_image)

        if not replaced:
            updated_images.append(image)

        updated_images.sort(key=lambda item: item.scene)
        payload["images"] = self._serialize_models(updated_images)
        payload["image_summary"] = self._build_image_summary(updated_images)
        payload["status"] = self._build_status(updated_images)
        payload["message"] = self._build_message(updated_images)

        try:
            self._write_json_atomic(target_path, payload)
        except OSError as exc:
            raise FileSaveError(f"Failed to save output file: {target_path}") from exc

    def _build_file_name(self) -> str:
        """Build an output file name using the required timestamp format."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"story_{timestamp}.json"

    def _write_json_atomic(self, target_path: Path, payload: dict[str, Any]) -> None:
        """Write JSON through a temporary file before replacing the target."""
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".tmp",
            dir=target_path.parent,
            delete=False,
        ) as temp_file:
            json.dump(payload, temp_file, ensure_ascii=False, indent=2)
            temp_file.write("\n")
            temp_path = Path(temp_file.name)

        temp_path.replace(target_path)

    def _serialize_models(self, models: list[BaseModel]) -> list[dict[str, Any]]:
        """Serialize Pydantic models to plain dictionaries."""
        return [model.model_dump() for model in models]

    def _is_safe_story_file_name(self, file_name: str) -> bool:
        """Allow only generated story JSON file names."""
        return (
            Path(file_name).name == file_name
            and file_name.startswith("story_")
            and file_name.endswith(".json")
        )

    def _build_image_summary(self, images: list[ImageResponse]) -> dict[str, Any]:
        """Build an image summary dictionary for saved story JSON."""
        return {
            "requested": any(image.status != "skipped" for image in images),
            "total": len(images),
            "succeeded": sum(1 for image in images if image.status == "success"),
            "failed": sum(1 for image in images if image.status == "failed"),
            "skipped": sum(1 for image in images if image.status == "skipped"),
        }

    def _build_status(self, images: list[ImageResponse]) -> str:
        """Build top-level story status from saved image records."""
        if not any(image.status != "skipped" for image in images):
            return "completed"

        if any(image.status == "failed" for image in images):
            return "partial"

        return "completed"

    def _build_message(self, images: list[ImageResponse]) -> str:
        """Build top-level story message from saved image records."""
        if any(image.status == "failed" for image in images):
            return "Story processed with one or more image failures."

        if any(image.status == "skipped" for image in images):
            return "Story and prompts generated. Generate images one scene at a time."

        return "Story processed successfully."
