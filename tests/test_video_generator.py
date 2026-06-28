"""Tests for cinematic video generation helpers."""

from pathlib import Path

from PIL import Image

from models.story import AudioResponse, ImageResponse, Scene
from services.video_generator import VideoGenerator


def test_video_generator_creates_video_from_scene_media(tmp_path, monkeypatch) -> None:
    output_root = tmp_path / "outputs"
    image_path = output_root / "images" / "scene_1.png"
    audio_path = output_root / "audio" / "scene_1.mp3"
    image_path.parent.mkdir(parents=True)
    audio_path.parent.mkdir(parents=True)
    Image.new("RGB", (64, 64), color=(12, 40, 90)).save(image_path)
    audio_path.write_bytes(b"fake mp3")

    def fake_write_video(self, scene_items, target_path):
        assert scene_items[0].image_path == image_path
        assert scene_items[0].audio_path == audio_path
        assert scene_items[0].duration_seconds == 3.25
        target_path.write_bytes(b"fake mp4")
        return 7.5

    monkeypatch.setattr(VideoGenerator, "_write_video_with_moviepy", fake_write_video)
    generator = VideoGenerator(
        output_dir=output_root / "videos",
        output_root=output_root,
        music_dir=tmp_path / "assets" / "music",
    )

    result = generator.create_video(
        scenes=[Scene(scene=1, description="A castle appears")],
        images=[
            ImageResponse(
                scene=1,
                status="success",
                image_path="outputs/images/scene_1.png",
            )
        ],
        audio=[
            AudioResponse(
                scene=1,
                status="success",
                audio_path="outputs/audio/scene_1.mp3",
                duration_seconds=3.25,
            )
        ],
        output_name="story_test.mp4",
    )

    assert result.video_path == (output_root / "videos" / "story_test.mp4").as_posix()
    assert result.duration_seconds == 7.5
    assert Path(result.video_path).exists()


def test_video_generator_uses_placeholder_when_image_is_missing(
    tmp_path,
    monkeypatch,
) -> None:
    output_root = tmp_path / "outputs"

    def fake_write_video(self, scene_items, target_path):
        assert scene_items[0].image_path.exists()
        assert scene_items[0].image_path.name == "video_scene_1.png"
        target_path.write_bytes(b"fake mp4")
        return 4.0

    monkeypatch.setattr(VideoGenerator, "_write_video_with_moviepy", fake_write_video)
    generator = VideoGenerator(
        output_dir=output_root / "videos",
        output_root=output_root,
        music_dir=tmp_path / "assets" / "music",
    )

    result = generator.create_video(
        scenes=[Scene(scene=1, description="Missing image scene")],
        images=[],
        audio=[],
        output_name="story_missing.mp4",
    )

    assert result.duration_seconds == 4.0
    assert Path(result.video_path).exists()


def test_video_generator_scales_scene_durations_to_target(
    tmp_path,
    monkeypatch,
) -> None:
    output_root = tmp_path / "outputs"
    image_path = output_root / "images" / "scene_1.png"
    image_path.parent.mkdir(parents=True)
    Image.new("RGB", (64, 64), color=(12, 40, 90)).save(image_path)

    def fake_write_video(self, scene_items, target_path):
        assert len(scene_items) == 2
        assert [round(item.duration_seconds, 2) for item in scene_items] == [
            8.75,
            8.75,
        ]
        target_path.write_bytes(b"fake mp4")
        return 20.0

    monkeypatch.setattr(VideoGenerator, "_write_video_with_moviepy", fake_write_video)
    generator = VideoGenerator(
        output_dir=output_root / "videos",
        output_root=output_root,
        music_dir=tmp_path / "assets" / "music",
        default_scene_duration=4.0,
        transition_seconds=0.5,
    )
    generator.title_duration = 2.0
    generator.credits_duration = 2.0

    result = generator.create_video(
        scenes=[
            Scene(scene=1, description="A castle appears"),
            Scene(scene=2, description="A princess finds a key"),
        ],
        images=[
            ImageResponse(
                scene=1,
                status="success",
                image_path="outputs/images/scene_1.png",
            ),
            ImageResponse(
                scene=2,
                status="success",
                image_path="outputs/images/scene_1.png",
            ),
        ],
        audio=[],
        output_name="story_target.mp4",
        target_duration_seconds=20,
    )

    assert result.duration_seconds == 20.0
    assert Path(result.video_path).exists()
