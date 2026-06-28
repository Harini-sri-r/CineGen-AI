"""Tests for Edge-TTS narration generation."""

import asyncio
from pathlib import Path
from types import SimpleNamespace

from models.story import Scene
from services.tts_generator import TTSGenerator


def test_tts_generator_saves_scene_audio(tmp_path, monkeypatch) -> None:
    saved_paths: list[str] = []

    class FakeCommunicate:
        def __init__(
            self,
            text,
            voice,
            *,
            rate,
            volume,
            pitch,
            connect_timeout,
            receive_timeout,
        ):
            self.text = text
            self.voice = voice
            self.rate = rate
            self.volume = volume
            self.pitch = pitch
            self.connect_timeout = connect_timeout
            self.receive_timeout = receive_timeout

        async def save(self, target_path: str) -> None:
            saved_paths.append(target_path)
            Path(target_path).write_bytes(b"fake mp3")

    monkeypatch.setitem(
        __import__("sys").modules,
        "edge_tts",
        SimpleNamespace(Communicate=FakeCommunicate),
    )
    monkeypatch.setattr(TTSGenerator, "_measure_audio_duration", lambda self, path: 2.5)

    generator = TTSGenerator(output_dir=tmp_path)
    audio = generator.generate_narrations(
        [Scene(scene=1, description="A young wizard enters a magical forest.")]
    )

    assert len(audio) == 1
    assert audio[0].status == "success"
    assert audio[0].duration_seconds == 2.5
    assert audio[0].audio_path == (tmp_path / "scene_1.mp3").as_posix()
    assert Path(saved_paths[0]).exists()


def test_tts_generator_returns_failed_audio_when_edge_tts_fails(
    tmp_path,
    monkeypatch,
) -> None:
    class FailingCommunicate:
        def __init__(self, *args, **kwargs):
            pass

        async def save(self, target_path: str) -> None:
            raise RuntimeError("tts unavailable")

    monkeypatch.setitem(
        __import__("sys").modules,
        "edge_tts",
        SimpleNamespace(Communicate=FailingCommunicate),
    )

    generator = TTSGenerator(output_dir=tmp_path)
    audio = generator.generate_narrations([Scene(scene=1, description="Opening scene")])

    assert audio[0].status == "failed"
    assert audio[0].audio_path is None
    assert "tts unavailable" in (audio[0].error or "")


def test_tts_generator_returns_failed_audio_when_scene_times_out(
    tmp_path,
    monkeypatch,
) -> None:
    class SlowCommunicate:
        def __init__(self, *args, **kwargs):
            pass

        async def save(self, target_path: str) -> None:
            await asyncio.sleep(1)

    monkeypatch.setitem(
        __import__("sys").modules,
        "edge_tts",
        SimpleNamespace(Communicate=SlowCommunicate),
    )

    generator = TTSGenerator(output_dir=tmp_path, scene_timeout_seconds=0.01)
    audio = generator.generate_narrations([Scene(scene=1, description="Opening scene")])

    assert audio[0].status == "failed"
    assert audio[0].audio_path is None
    assert "timed out" in (audio[0].error or "").lower()
