"""Tests for scene extraction."""

from services.scene_generator import SceneGenerator


def test_extract_scenes_splits_sentences_and_numbers_them() -> None:
    generator = SceneGenerator()

    scenes = generator.extract_scenes(
        "A girl enters a magical forest. She finds a glowing deer!\n"
        "The deer guides her to a waterfall?"
    )

    assert [scene.scene for scene in scenes] == [1, 2, 3]
    assert [scene.description for scene in scenes] == [
        "A girl enters a magical forest",
        "She finds a glowing deer",
        "The deer guides her to a waterfall",
    ]


def test_extract_scenes_ignores_blank_segments() -> None:
    generator = SceneGenerator()

    scenes = generator.extract_scenes("First scene.\n\n   Second scene.")

    assert len(scenes) == 2
    assert scenes[0].description == "First scene"
    assert scenes[1].description == "Second scene"
