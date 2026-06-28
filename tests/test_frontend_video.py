"""Static checks for frontend video rendering wiring."""

import json
from pathlib import Path


def test_frontend_contains_video_dashboard_elements() -> None:
    html = Path("index.html").read_text(encoding="utf-8")

    assert 'onsubmit="return false;"' in html
    assert 'id="generateButton" class="primary-button" type="button"' in html
    assert 'id="videoPanel"' in html
    assert 'id="videoStatusBadge"' in html
    assert 'id="downloadVideoButton"' in html
    assert 'id="targetDurationInput"' in html
    assert 'name="target_duration_seconds"' in html
    assert "Download MP4" in html


def test_frontend_script_contains_video_generation_flow() -> None:
    script = Path("script.js").read_text(encoding="utf-8")

    assert "DEFAULT_API_BASE_URL" in script
    assert "FALLBACK_API_BASE_URLS" in script
    assert "API_DISCOVERY_TIMEOUT_MS" in script
    assert 'const DEFAULT_API_BASE_URL = "http://127.0.0.1:8001";' in script
    assert 'const FALLBACK_API_BASE_URLS = ["http://127.0.0.1:8003"];' in script
    assert "activeApiBaseUrl" in script
    assert "ensureApiBaseUrl" in script
    assert "getApiBaseUrlCandidates" in script
    assert "fetchWithTimeout" in script
    assert "isBackendConnectionError" in script
    assert "GENERATE_VIDEO_ENDPOINT" in script
    assert 'storyForm.addEventListener("submit", handleStoryGeneration)' in script
    assert 'generateButton.addEventListener("click", handleStoryGeneration)' in script
    assert "event?.preventDefault()" in script
    assert "event?.stopPropagation()" in script
    assert "let isStoryGenerating = false;" in script
    assert "let isVideoGenerating = false;" in script
    assert 'button.addEventListener("click", async (event) =>' in script
    assert "event.preventDefault();" in script
    assert "event.stopPropagation();" in script
    assert "generateVideoForLatestResult" in script
    assert "generateVideoFromResult" in script
    assert "canGenerateVideo" in script
    assert "getTargetDurationSeconds" in script
    assert "target_duration_seconds" in script
    assert "document.createElement(\"video\")" in script
    assert "video.controls = true" in script
    assert "Generate MP4" in script
    assert "downloadVideo" in script


def test_frontend_only_successful_images_drive_downloads_and_video() -> None:
    script = Path("script.js").read_text(encoding="utf-8")

    assert 'image.status === "success" &&' in script
    assert "formatImageError(image.error)" in script
    assert "formatImageWarning(image.warning)" in script
    assert "Storyboard fallback" in script
    assert "Pollinations timed out while generating the image" in script
    assert 'image.status !== "skipped" &&' not in script


def test_live_server_ignores_generated_outputs() -> None:
    settings = json.loads(Path(".vscode/settings.json").read_text(encoding="utf-8"))

    assert "**/outputs/**" in settings["liveServer.settings.ignoreFiles"]
    assert settings["files.watcherExclude"]["**/outputs/**"] is True
