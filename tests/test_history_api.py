"""Tests for saved generation history endpoints."""

import json

from fastapi.testclient import TestClient

import routes.history as history_routes
from app import app
from services.history_service import HistoryService


def test_history_lists_valid_files_newest_first(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(history_routes, "history_service", HistoryService(tmp_path))
    _write_story_file(tmp_path / "story_20260624_173228.json", story="Newest")
    _write_story_file(tmp_path / "story_20260623_153814.json", story="Older")
    (tmp_path / "story_20260625_120000.json").write_text("{bad", encoding="utf-8")
    (tmp_path / "notes.json").write_text("{}", encoding="utf-8")
    client = TestClient(app)

    response = client.get("/history")

    assert response.status_code == 200
    assert response.json() == [
        {
            "file": "story_20260624_173228.json",
            "created_at": "2026-06-24 17:32:28",
        },
        {
            "file": "story_20260623_153814.json",
            "created_at": "2026-06-23 15:38:14",
        },
    ]


def test_history_detail_returns_saved_story(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(history_routes, "history_service", HistoryService(tmp_path))
    _write_story_file(tmp_path / "story_20260624_173228.json", story="Saved story")
    client = TestClient(app)

    response = client.get("/history/story_20260624_173228.json")
    data = response.json()

    assert response.status_code == 200
    assert data["story"] == "Saved story"
    assert data["scenes"][0]["description"] == "Scene one"
    assert data["prompts"][0]["prompt"] == "cinematic scene one"
    assert data["images"][0]["status"] == "success"
    assert data["images"][0]["image_url"].endswith("/outputs/images/test.png")


def test_history_detail_repairs_missing_image_with_placeholder(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(history_routes, "history_service", HistoryService(tmp_path))
    _write_story_file(
        tmp_path / "story_20260624_173228.json",
        story="Saved story",
        create_image=False,
    )
    client = TestClient(app)

    response = client.get("/history/story_20260624_173228.json")
    data = response.json()

    repaired_path = tmp_path / "images" / "test.png"
    assert response.status_code == 200
    assert data["images"][0]["status"] == "failed"
    assert data["images"][0]["image_path"] == "outputs/images/test.png"
    assert data["images"][0]["image_url"].endswith("/outputs/images/test.png")
    assert repaired_path.exists()


def test_history_detail_missing_file_returns_404(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(history_routes, "history_service", HistoryService(tmp_path))
    client = TestClient(app)

    response = client.get("/history/story_20260624_173228.json")

    assert response.status_code == 404
    assert response.json()["detail"] == "History file not found."


def test_history_stats_counts_valid_outputs(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(history_routes, "history_service", HistoryService(tmp_path))
    _write_story_file(tmp_path / "story_20260624_173228.json", story="One")
    _write_story_file(tmp_path / "story_20260624_173229.json", story="Two")
    (tmp_path / "story_20260624_173230.json").write_text("{}", encoding="utf-8")
    client = TestClient(app)

    response = client.get("/history/stats")

    assert response.status_code == 200
    assert response.json() == {
        "total_stories": 2,
        "total_scenes": 2,
        "total_images": 2,
    }


def _write_story_file(path, story: str, create_image: bool = True) -> None:
    if create_image:
        image_path = path.parent / "images" / "test.png"
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(b"image")

    path.write_text(
        json.dumps(
            {
                "success": True,
                "status": "completed",
                "message": "Story processed successfully.",
                "story": story,
                "scenes": [{"scene": 1, "description": "Scene one"}],
                "prompts": [{"scene": 1, "prompt": "cinematic scene one"}],
                "images": [
                    {
                        "scene": 1,
                        "status": "success",
                        "image_path": "outputs/images/test.png",
                        "error": None,
                    }
                ],
                "image_summary": {
                    "requested": True,
                    "total": 1,
                    "succeeded": 1,
                    "failed": 0,
                    "skipped": 0,
                },
            }
        ),
        encoding="utf-8",
    )
