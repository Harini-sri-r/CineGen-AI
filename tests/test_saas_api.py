"""Tests for protected SaaS dashboard, history, profile, settings, and video APIs."""

from collections.abc import Iterable

from fastapi.testclient import TestClient

import routes.generate as generate_routes
import routes.video as video_routes
from app import app
from models.story import AudioResponse, ImageResponse, Prompt, Scene
from services.scene_generator import SceneGenerator
from services.video_generator import VideoRenderResult
from tests.conftest_saas import (
    auth_headers,
    clear_test_database_override,
    register_user,
    use_test_database,
)
from utils.file_handler import FileHandler


def test_authenticated_generation_populates_user_dashboard_and_history(
    tmp_path,
    monkeypatch,
) -> None:
    use_test_database(tmp_path)
    monkeypatch.setattr(generate_routes, "file_handler", FileHandler(tmp_path / "outputs"))
    monkeypatch.setattr(generate_routes, "scene_generator", SceneGenerator())
    client = TestClient(app)
    token_data = register_user(client)

    response = client.post(
        "/generate-story",
        json={
            "story": "A girl enters a magical forest. She finds a glowing deer.",
            "text_only": True,
        },
        headers=auth_headers(token_data),
    )
    assert response.status_code == 200

    dashboard = client.get("/api/dashboard", headers=auth_headers(token_data)).json()
    assert dashboard["stats"]["total_stories"] == 1
    assert dashboard["recent_stories"][0]["title"]

    history = client.get("/api/history", headers=auth_headers(token_data)).json()
    assert history["total"] == 1
    story_id = history["items"][0]["story_id"]

    detail = client.get(
        f"/api/stories/{story_id}",
        headers=auth_headers(token_data),
    ).json()
    assert "magical forest" in detail["story"]
    assert len(detail["scenes"]) >= 2

    other_user = register_user(client, email="other@example.com")
    forbidden_detail = client.get(
        f"/api/stories/{story_id}",
        headers=auth_headers(other_user),
    )
    assert forbidden_detail.status_code == 404
    clear_test_database_override()


def test_profile_and_settings_can_be_updated(tmp_path) -> None:
    use_test_database(tmp_path)
    client = TestClient(app)
    token_data = register_user(client)
    headers = auth_headers(token_data)

    profile_response = client.put(
        "/api/profile",
        json={"username": "filmmaker", "email": "filmmaker@example.com"},
        headers=headers,
    )
    assert profile_response.status_code == 200
    assert profile_response.json()["user"]["username"] == "filmmaker"

    settings_response = client.put(
        "/api/settings",
        json={
            "theme": "light",
            "language": "en",
            "voice_selection": "en-US-JennyNeural",
            "image_provider": "pollinations",
            "background_music_enabled": False,
        },
        headers=headers,
    )
    assert settings_response.status_code == 200
    assert settings_response.json()["theme"] == "light"
    assert settings_response.json()["background_music_enabled"] is False
    clear_test_database_override()


def test_authenticated_video_generation_populates_video_library(
    tmp_path,
    monkeypatch,
) -> None:
    use_test_database(tmp_path)
    monkeypatch.setattr(video_routes, "file_handler", FileHandler(tmp_path / "outputs"))
    monkeypatch.setattr(video_routes, "scene_generator", SceneGenerator())
    monkeypatch.setattr(
        video_routes,
        "_media_generators_for_user",
        lambda user, story_key: (
            video_routes.image_generator,
            video_routes.tts_generator,
            video_routes.video_generator,
        ),
    )

    def fake_generate_images(prompts: Iterable[Prompt]) -> list[ImageResponse]:
        return [
            ImageResponse(
                scene=prompt.scene,
                status="success",
                image_path=f"outputs/images/scene_{prompt.scene}.png",
                image_url=f"http://testserver/outputs/images/scene_{prompt.scene}.png",
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
        return VideoRenderResult(
            video_path=f"outputs/videos/{output_name}",
            duration_seconds=float(target_duration_seconds),
        )

    monkeypatch.setattr(video_routes.image_generator, "generate_images", fake_generate_images)
    monkeypatch.setattr(
        video_routes.tts_generator,
        "generate_narrations",
        fake_generate_narrations,
    )
    monkeypatch.setattr(video_routes.video_generator, "create_video", fake_create_video)

    client = TestClient(app)
    token_data = register_user(client)
    headers = auth_headers(token_data)

    response = client.post(
        "/generate-video",
        json={
            "story": "A boy eats ice cream outside a small shop.",
            "target_duration_seconds": 20,
        },
        headers=headers,
    )
    assert response.status_code == 200

    videos = client.get("/api/videos", headers=headers).json()
    assert videos["total"] == 1
    assert videos["items"][0]["duration"] == 20.0
    assert videos["items"][0]["video_url"].endswith(".mp4")
    clear_test_database_override()
