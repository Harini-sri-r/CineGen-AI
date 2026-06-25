"""LLM-backed scene extraction service using local Ollama."""

from __future__ import annotations

import json
import os
from socket import timeout as SocketTimeout
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from pydantic import ValidationError

from models.story import Scene
from services.scene_generator import SceneGenerator
from utils.logger import get_logger

logger = get_logger(__name__)

HttpClient = Callable[[str, dict[str, Any], float], dict[str, Any]]


class LLMSceneGenerationError(RuntimeError):
    """Raised when Ollama scene extraction cannot produce valid scenes."""


class LLMSceneGenerator:
    """Extract story scenes with Ollama and fall back to rule-based extraction."""

    _scene_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "scenes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "scene": {"type": "integer"},
                        "description": {"type": "string"},
                    },
                    "required": ["scene", "description"],
                },
            }
        },
        "required": ["scenes"],
    }

    def __init__(
        self,
        fallback_generator: SceneGenerator | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
        temperature: float | None = None,
        keep_alive: str | None = None,
        http_client: HttpClient | None = None,
    ) -> None:
        self.fallback_generator = fallback_generator or SceneGenerator()
        self.base_url = self._normalize_base_url(
            base_url
            or os.getenv("CINEGEN_OLLAMA_BASE_URL")
            or os.getenv("OLLAMA_HOST")
            or "http://127.0.0.1:11434"
        )
        self.model = model or os.getenv("CINEGEN_OLLAMA_MODEL", "llama3")
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else self._env_float("CINEGEN_OLLAMA_TIMEOUT_SECONDS", 60.0)
        )
        self.temperature = (
            temperature
            if temperature is not None
            else self._env_float("CINEGEN_OLLAMA_TEMPERATURE", 0.0)
        )
        self.keep_alive = keep_alive or os.getenv("CINEGEN_OLLAMA_KEEP_ALIVE", "5m")
        self.http_client = http_client or self._post_json

    def extract_scenes(self, story: str) -> list[Scene]:
        """Extract scenes with Ollama, using rule-based extraction on failure."""
        story_text = story.strip()
        if not story_text:
            return []

        try:
            scenes = self._extract_with_ollama(story_text)
        except LLMSceneGenerationError as exc:
            logger.warning("LLM scene extraction failed; using fallback: %s", exc)
            return self._fallback_extract(story_text)

        logger.info(
            "LLM scene extraction completed: model=%s scenes=%s",
            self.model,
            len(scenes),
        )
        return scenes

    def _extract_with_ollama(self, story: str) -> list[Scene]:
        """Call Ollama and parse a validated scene list."""
        endpoint = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "system": (
                "You are a deterministic JSON information extraction engine. "
                "You split stories into factual scene descriptions without "
                "adding details."
            ),
            "prompt": self._build_prompt(story),
            "stream": False,
            "format": self._scene_schema,
            "options": {"temperature": self.temperature},
            "keep_alive": self.keep_alive,
        }

        logger.info(
            "LLM scene extraction started: endpoint=%s model=%s timeout=%ss",
            endpoint,
            self.model,
            self.timeout_seconds,
        )

        try:
            response_payload = self.http_client(endpoint, payload, self.timeout_seconds)
        except LLMSceneGenerationError:
            raise
        except (TimeoutError, SocketTimeout) as exc:
            raise LLMSceneGenerationError("Ollama request timed out.") from exc
        except Exception as exc:
            raise LLMSceneGenerationError(f"Ollama request failed: {exc}") from exc

        response_text = str(response_payload.get("response", "")).strip()
        if not response_text:
            raise LLMSceneGenerationError("Ollama returned an empty response.")

        return self._parse_scenes(response_text)

    def _fallback_extract(self, story: str) -> list[Scene]:
        """Use the existing punctuation-based scene extractor."""
        scenes = self.fallback_generator.extract_scenes(story)
        logger.info("Fallback scene extraction completed: %s scenes", len(scenes))
        return scenes

    def _build_prompt(self, story: str) -> str:
        """Build a strict JSON scene extraction prompt for Ollama."""
        return (
            "Split the story into factual scenes.\n\n"
            "Rules:\n"
            "1. Preserve story order.\n"
            "2. Use exactly one scene for each distinct event, usually one per sentence.\n"
            "3. Do not split a single sentence into multiple scenes.\n"
            "4. Do not invent clothing, appearance, props, emotions, locations, "
            "actions, atmosphere, or camera details.\n"
            "5. Scene descriptions must be copied or minimally rephrased from the "
            "story only.\n"
            "6. Keep descriptions short.\n\n"
            "Example story:\n"
            "A girl enters a magical forest. She discovers a glowing deer. "
            "The deer guides her to a hidden waterfall.\n\n"
            "Example JSON:\n"
            '{"scenes":[{"scene":1,"description":"A girl enters a magical forest"},'
            '{"scene":2,"description":"A glowing deer appears"},'
            '{"scene":3,"description":"The deer guides her to a hidden waterfall"}]}\n\n'
            "Return JSON only with this exact shape:\n"
            '{"scenes":[{"scene":1,"description":"Scene description"}]}\n\n'
            "Story:\n"
            f"{story}"
        )

    def _parse_scenes(self, response_text: str) -> list[Scene]:
        """Parse Ollama JSON into sequential Scene models."""
        payload = self._load_json_response(response_text)

        if isinstance(payload, dict):
            raw_scenes = payload.get("scenes")
        elif isinstance(payload, list):
            raw_scenes = payload
        else:
            raw_scenes = None

        if not isinstance(raw_scenes, list):
            raise LLMSceneGenerationError("Ollama response did not contain scenes.")

        scenes: list[Scene] = []
        for index, item in enumerate(raw_scenes, start=1):
            if not isinstance(item, dict):
                logger.warning("Ignoring non-object LLM scene item: %r", item)
                continue

            description = self._clean_description(str(item.get("description", "")))
            if not description:
                logger.warning("Ignoring LLM scene with empty description: %r", item)
                continue

            try:
                scenes.append(Scene(scene=index, description=description))
            except ValidationError as exc:
                logger.warning("Ignoring invalid LLM scene item %r: %s", item, exc)

        if not scenes:
            raise LLMSceneGenerationError("Ollama returned no valid scenes.")

        return scenes

    def _load_json_response(self, response_text: str) -> Any:
        """Load JSON, with a small recovery path for fenced or prefixed output."""
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            extracted_json = self._extract_json_segment(response_text)
            if extracted_json is None:
                raise LLMSceneGenerationError("Ollama response was not valid JSON.")

            try:
                return json.loads(extracted_json)
            except json.JSONDecodeError as exc:
                raise LLMSceneGenerationError(
                    "Ollama response JSON segment was invalid."
                ) from exc

    def _extract_json_segment(self, text: str) -> str | None:
        """Extract the first plausible JSON object or array from model output."""
        object_start = text.find("{")
        object_end = text.rfind("}")
        array_start = text.find("[")
        array_end = text.rfind("]")

        candidates: list[str] = []
        if object_start != -1 and object_end > object_start:
            candidates.append(text[object_start : object_end + 1])
        if array_start != -1 and array_end > array_start:
            candidates.append(text[array_start : array_end + 1])

        return candidates[0] if candidates else None

    def _post_json(
        self,
        endpoint: str,
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        """POST a JSON payload to Ollama and return the decoded JSON response."""
        request = Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                raw_body = response.read().decode("utf-8")
        except (TimeoutError, SocketTimeout) as exc:
            raise LLMSceneGenerationError("Ollama request timed out.") from exc
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise LLMSceneGenerationError(
                f"Ollama returned HTTP {exc.code}: {detail}"
            ) from exc
        except URLError as exc:
            raise LLMSceneGenerationError(f"Ollama is unavailable: {exc.reason}") from exc
        except OSError as exc:
            raise LLMSceneGenerationError(f"Ollama request failed: {exc}") from exc

        try:
            decoded = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise LLMSceneGenerationError("Ollama HTTP response was not JSON.") from exc

        if not isinstance(decoded, dict):
            raise LLMSceneGenerationError("Ollama HTTP response was not an object.")

        return decoded

    def _clean_description(self, description: str) -> str:
        """Normalize scene descriptions from the LLM."""
        return " ".join(description.split()).rstrip(".!?;:").strip()

    def _normalize_base_url(self, base_url: str) -> str:
        """Normalize configured Ollama host values into an HTTP base URL."""
        cleaned_url = base_url.strip().rstrip("/")
        parsed = urlparse(cleaned_url)

        if parsed.scheme:
            return cleaned_url

        return f"http://{cleaned_url}"

    def _env_float(self, name: str, default: float) -> float:
        """Read a float environment variable with a safe fallback."""
        raw_value = os.getenv(name)
        if raw_value is None:
            return default

        try:
            return float(raw_value)
        except ValueError:
            logger.warning(
                "Invalid float env var %s=%r; using %s",
                name,
                raw_value,
                default,
            )
            return default
