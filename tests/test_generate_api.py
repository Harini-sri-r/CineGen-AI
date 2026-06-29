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
    assert data["image_summary"]["succeeded"] >= 3
    assert len(data["images"]) >= 3
    assert data["images"][0]["status"] == "success"
    assert data["images"][0]["image_path"] == "outputs/images/test_scene_1.png"
    assert "A boy eats ice cream" in data["story"]
    assert data["target_duration_seconds"] == 30


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
    assert data["image_summary"]["total"] >= 3
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
            provider="storyboard",
            warning="Hosted image providers failed, so CineGen rendered a local storyboard fallback.",
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
    assert data["success"] is True
    assert data["scene"] == 1
    assert data["status"] == "success"
    assert data["image_path"] == "outputs/images/scene_1.png"
    assert data["image_url"].startswith("http://testserver/outputs/images/scene_1.png")
    assert data["provider"] == "storyboard"
    assert "storyboard fallback" in data["warning"]
    assert data["error"] is None

    saved_payload = json.loads((tmp_path / file_name).read_text(encoding="utf-8"))
    assert saved_payload["images"][0]["status"] == "success"
    assert saved_payload["images"][0]["image_url"] == data["image_url"]
    assert saved_payload["images"][0]["provider"] == "storyboard"
    assert saved_payload["images"][0]["warning"] == data["warning"]


def test_generate_story_rejects_short_story() -> None:
    client = TestClient(app)

    response = client.post(
        "/generate-story",
        json={"story": "hi", "text_only": True},
    )

    assert response.status_code == 422


def test_generate_story_expands_short_idea(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(generate_routes, "file_handler", FileHandler(tmp_path))
    monkeypatch.setattr(generate_routes, "fast_scene_generator", SceneGenerator())

    class SlowSceneGenerator:
        def extract_scenes(self, story: str):
            raise AssertionError("short ideas should use fast scene extraction")

    monkeypatch.setattr(generate_routes, "scene_generator", SlowSceneGenerator())
    client = TestClient(app)

    response = client.post(
        "/generate-story",
        json={
            "story": "princess story",
            "text_only": True,
            "target_duration_seconds": 20,
        },
    )
    data = response.json()

    assert response.status_code == 200
    assert data["story"].count(".") == 4
    assert "a princess" in data["story"]
    assert data["target_duration_seconds"] == 20
    assert len(data["scenes"]) == 4
