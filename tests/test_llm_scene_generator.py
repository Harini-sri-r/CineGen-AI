"""Tests for Ollama-backed scene extraction."""

from typing import Any

from services.llm_scene_generator import LLMSceneGenerator
from services.scene_generator import SceneGenerator


def test_llm_scene_generator_uses_ollama_structured_response() -> None:
    def fake_http_client(
        endpoint: str,
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        assert endpoint == "http://127.0.0.1:11434/api/generate"
        assert payload["model"] == "llama3"
        assert payload["stream"] is False
        assert "format" in payload
        assert timeout_seconds == 60.0
        return {
            "response": (
                '{"scenes":['
                '{"scene":1,"description":"A girl enters a magical forest."},'
                '{"scene":2,"description":"A glowing deer appears."},'
                '{"scene":3,"description":"The deer guides her to a hidden waterfall."}'
                "]}"
            )
        }

    generator = LLMSceneGenerator(http_client=fake_http_client)

    scenes = generator.extract_scenes(
        "A girl enters a magical forest. She discovers a glowing deer. "
        "The deer guides her to a hidden waterfall."
    )

    assert [scene.scene for scene in scenes] == [1, 2, 3]
    assert [scene.description for scene in scenes] == [
        "A girl enters a magical forest",
        "A glowing deer appears",
        "The deer guides her to a hidden waterfall",
    ]


def test_llm_scene_generator_accepts_top_level_array_response() -> None:
    def fake_http_client(
        endpoint: str,
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        return {
            "response": (
                "["
                '{"scene":1,"description":"Opening image"},'
                '{"scene":2,"description":"Final image"}'
                "]"
            )
        }

    generator = LLMSceneGenerator(http_client=fake_http_client)

    scenes = generator.extract_scenes("Opening image. Final image.")

    assert [scene.description for scene in scenes] == [
        "Opening image",
        "Final image",
    ]


def test_llm_scene_generator_falls_back_when_ollama_unavailable() -> None:
    def fake_http_client(
        endpoint: str,
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        raise TimeoutError("simulated timeout")

    generator = LLMSceneGenerator(
        fallback_generator=SceneGenerator(),
        http_client=fake_http_client,
    )

    scenes = generator.extract_scenes("First scene. Second scene.")

    assert [scene.description for scene in scenes] == ["First scene", "Second scene"]


def test_llm_scene_generator_falls_back_for_invalid_model_output() -> None:
    def fake_http_client(
        endpoint: str,
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        return {"response": "not json"}

    generator = LLMSceneGenerator(
        fallback_generator=SceneGenerator(),
        http_client=fake_http_client,
    )

    scenes = generator.extract_scenes("A scene starts. Another scene follows.")

    assert [scene.description for scene in scenes] == [
        "A scene starts",
        "Another scene follows",
    ]


def test_llm_scene_generator_reads_environment_configuration(monkeypatch) -> None:
    monkeypatch.setenv("CINEGEN_OLLAMA_BASE_URL", "http://localhost:11434/")
    monkeypatch.setenv("CINEGEN_OLLAMA_MODEL", "llama3:8b")
    monkeypatch.setenv("CINEGEN_OLLAMA_TIMEOUT_SECONDS", "7.5")
    monkeypatch.setenv("CINEGEN_OLLAMA_TEMPERATURE", "0.2")
    monkeypatch.setenv("CINEGEN_OLLAMA_KEEP_ALIVE", "10m")

    generator = LLMSceneGenerator(http_client=lambda endpoint, payload, timeout: {})

    assert generator.base_url == "http://localhost:11434"
    assert generator.model == "llama3:8b"
    assert generator.timeout_seconds == 7.5
    assert generator.temperature == 0.2
    assert generator.keep_alive == "10m"
