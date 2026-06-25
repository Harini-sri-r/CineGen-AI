"""Tests for the story generation API endpoint."""

import json
from collections.abc import Iterable

from fastapi.testclient import TestClient

import routes.generate as generate_routes
from app import app
from models.story import ImageResponse, Prompt
from services.scene_generator import SceneGenerator
from utils.file_handler import FileHandler


def test_generate_story_text_only_returns_skipped_images(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(generate_routes, "file_handler", FileHandler(tmp_path))
    monkeypatch.setattr(generate_routes, "scene_generator", SceneGenerator())
    client = TestClient(app)

    response = client.post(
        "/generate-story",
        json={
            "story": "A girl enters a magical forest. She finds a glowing deer.",
            "text_only": True,
        },
    )

    data = response.json()

    assert response.status_code == 200
    assert data["status"] == "text_only"
    assert data["image_summary"] == {
        "requested": False,
        "total": 2,
        "succeeded": 0,
        "failed": 0,
        "skipped": 2,
    }
    assert all(image["status"] == "skipped" for image in data["images"])
    assert (tmp_path / data["file_name"]).exists()


def test_generate_story_with_images_returns_success_records(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(generate_routes, "file_handler", FileHandler(tmp_path))
    monkeypatch.setattr(generate_routes, "scene_generator", SceneGenerator())

    def fake_generate_images(prompts: Iterable[Prompt]) -> list[ImageResponse]:
        return [
            ImageResponse(
                scene=prompt.scene,
                status="success",
                image_path=f"outputs/images/test_scene_{prompt.scene}.png",
                error=None,
            )
            for prompt in prompts
        ]

    monkeypatch.setattr(
        generate_routes.image_generator,
        "generate_images",
        fake_generate_images,
    )
    client = TestClient(app)

    response = client.post(
        "/generate-story",
        json={
            "story": "A boy eats ice cream outside a small shop.",
            "text_only": False,
        },
    )

    data = response.json()

    assert response.status_code == 200
    assert data["status"] == "completed"
    assert data["image_summary"]["requested"] is True
    assert data["image_summary"]["succeeded"] == 1
    assert data["images"][0]["status"] == "success"
    assert data["images"][0]["image_path"] == "outputs/images/test_scene_1.png"


def test_generate_story_can_defer_images_for_per_scene_generation(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(generate_routes, "file_handler", FileHandler(tmp_path))
    monkeypatch.setattr(generate_routes, "scene_generator", SceneGenerator())

    def fail_if_called(prompts: Iterable[Prompt]) -> list[ImageResponse]:
        raise AssertionError("batch image generation should be deferred")

    monkeypatch.setattr(
        generate_routes.image_generator,
        "generate_images",
        fail_if_called,
    )
    client = TestClient(app)

    response = client.post(
        "/generate-story",
        json={
            "story": "A boy eats ice cream outside a small shop.",
            "text_only": False,
            "defer_images": True,
        },
    )
    data = response.json()

    assert response.status_code == 200
    assert data["status"] == "completed"
    assert data["image_summary"]["requested"] is True
    assert data["image_summary"]["succeeded"] == 0
    assert data["images"][0]["status"] == "skipped"
    assert "one scene at a time" in data["message"]


def test_generate_image_returns_single_scene_response_and_updates_history(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(generate_routes, "file_handler", FileHandler(tmp_path))
    monkeypatch.setattr(generate_routes, "scene_generator", SceneGenerator())
    client = TestClient(app)

    story_response = client.post(
        "/generate-story",
        json={
            "story": "A boy eats ice cream outside a small shop.",
            "text_only": False,
            "defer_images": True,
        },
    )
    file_name = story_response.json()["file_name"]

    def fake_generate_image_with_fallback(prompt: str, scene: int) -> ImageResponse:
        return ImageResponse(
            scene=scene,
            status="success",
            image_path=f"outputs/images/scene_{scene}.png",
            image_url=None,
            error=None,
        )

    monkeypatch.setattr(
        generate_routes.image_generator,
        "generate_image_with_fallback",
        fake_generate_image_with_fallback,
    )

    response = client.post(
        "/generate-image",
        json={
            "scene": 1,
            "prompt": "cinematic ice cream shop",
            "file_name": file_name,
        },
    )
    data = response.json()

    assert response.status_code == 200
    assert data == {
        "success": True,
        "scene": 1,
        "status": "success",
        "image_path": "outputs/images/scene_1.png",
        "image_url": "http://testserver/outputs/images/scene_1.png",
        "error": None,
    }

    saved_payload = json.loads((tmp_path / file_name).read_text(encoding="utf-8"))
    assert saved_payload["images"][0]["status"] == "success"
    assert saved_payload["images"][0]["image_url"] == data["image_url"]


def test_generate_story_rejects_short_story() -> None:
    client = TestClient(app)

    response = client.post(
        "/generate-story",
        json={"story": "short", "text_only": True},
    )

    assert response.status_code == 422
