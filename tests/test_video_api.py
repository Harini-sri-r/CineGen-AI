"""Tests for the story-to-video API endpoint."""

import json
from collections.abc import Iterable

from fastapi.testclient import TestClient

import routes.video as video_routes
from app import app
from models.story import AudioResponse, ImageResponse, Prompt, Scene
from services.scene_generator import SceneGenerator
from services.video_generator import VideoRenderResult
from utils.file_handler import FileHandler


def test_generate_video_returns_mp4_metadata_and_saves_history(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(video_routes, "file_handler", FileHandler(tmp_path))
    monkeypatch.setattr(video_routes, "scene_generator", SceneGenerator())

    def fake_generate_images(prompts: Iterable[Prompt]) -> list[ImageResponse]:
        return [
            ImageResponse(
                scene=prompt.scene,
                status="success",
                image_path=f"outputs/images/scene_{prompt.scene}.png",
            )
            for prompt in prompts
        ]

    def fake_generate_narrations(scenes: Iterable[Scene]) -> list[AudioResponse]:
        return [
            AudioResponse(
                scene=scene.scene,
                status="success",
                audio_path=f"outputs/audio/scene_{scene.scene}.mp3",
                duration_seconds=2.0,
            )
            for scene in scenes
        ]

    def fake_create_video(scenes, images, audio, output_name, target_duration_seconds):
        assert output_name.endswith(".mp4")
        assert target_duration_seconds == 20
        return VideoRenderResult(
            video_path=f"outputs/videos/{output_name}",
            duration_seconds=20.0,
        )

    monkeypatch.setattr(video_routes.image_generator, "generate_images", fake_generate_images)
    monkeypatch.setattr(
        video_routes.tts_generator,
        "generate_narrations",
        fake_generate_narrations,
    )
    monkeypatch.setattr(video_routes.video_generator, "create_video", fake_create_video)

    client = TestClient(app)
    response = client.post(
        "/generate-video",
        json={
            "story": "A boy eats ice cream outside a small shop.",
            "target_duration_seconds": 20,
        },
    )
    data = response.json()

    assert response.status_code == 200
    assert data["success"] is True
    assert data["video_url"].endswith(".mp4")
    assert data["duration"] == "20 seconds"
    assert data["target_duration_seconds"] == 20
    assert data["scene_count"] >= 3
    assert data["audio"][0]["audio_url"].endswith("/outputs/audio/scene_1.mp3")

    saved_payload = json.loads((tmp_path / data["file_name"]).read_text("utf-8"))
    assert saved_payload["video_path"].endswith(".mp4")
    assert saved_payload["audio"][0]["audio_path"] == "outputs/audio/scene_1.mp3"
    assert saved_payload["target_duration_seconds"] == 20
    assert saved_payload["generation_duration_seconds"] >= 0


def test_generate_video_rejects_all_failed_images(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(video_routes, "file_handler", FileHandler(tmp_path))
    monkeypatch.setattr(video_routes, "scene_generator", SceneGenerator())

    def fake_generate_images(prompts: Iterable[Prompt]) -> list[ImageResponse]:
        return [
            ImageResponse(
                scene=prompt.scene,
                status="failed",
                image_path=f"outputs/images/scene_{prompt.scene}.png",
                error="Image provider timed out.",
            )
            for prompt in prompts
        ]

    def fail_if_video_is_rendered(*args, **kwargs):
        raise AssertionError("video should not render without successful images")

    monkeypatch.setattr(video_routes.image_generator, "generate_images", fake_generate_images)
    monkeypatch.setattr(video_routes.video_generator, "create_video", fail_if_video_is_rendered)

    client = TestClient(app)
    response = client.post(
        "/generate-video",
        json={"story": "A boy eats ice cream outside a small shop."},
    )
    data = response.json()

    assert response.status_code == 400
    assert data["detail"] == (
        "Generate at least one successful scene image before creating a video."
    )
