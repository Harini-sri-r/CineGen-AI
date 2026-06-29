"""Tests for short idea story composition."""

from services.story_composer import StoryComposer


def test_story_composer_expands_short_idea_for_target_duration() -> None:
    composer = StoryComposer()

    story = composer.compose("princess story", target_duration_seconds=30)

    assert "a princess" in story
    assert story.count(".") == 5
    assert any(term in story for term in ("castle", "kingdom", "tower", "village"))
    assert "final challenge" not in story


def test_story_composer_keeps_ending_for_short_video() -> None:
    composer = StoryComposer()

    story = composer.compose("lost robot", target_duration_seconds=20)

    assert story.count(".") == 4
    assert "lost robot" in story
    assert "workshop" in story or "city" in story or "machine" in story
    assert "final challenge" not in story


def test_story_composer_varies_short_ideas_by_theme() -> None:
    composer = StoryComposer()

    princess_story = composer.compose("princess story", target_duration_seconds=30)
    robot_story = composer.compose("lost robot", target_duration_seconds=30)
    pirate_story = composer.compose("pirate island adventure", target_duration_seconds=30)

    assert princess_story != robot_story
    assert robot_story != pirate_story
    assert any(term in princess_story for term in ("castle", "kingdom", "tower", "village"))
    assert "workshop" in robot_story or "machine" in robot_story
    assert "ship" in pirate_story or "island" in pirate_story or "harbor" in pirate_story


def test_story_composer_keeps_one_sentence_premise_when_expanding() -> None:
    composer = StoryComposer()

    story = composer.compose(
        "A boy eats ice cream outside a small shop.",
        target_duration_seconds=30,
    )

    assert story.startswith("A boy eats ice cream outside a small shop.")
    assert story.count(".") == 5


def test_story_composer_preserves_existing_two_sentence_story() -> None:
    composer = StoryComposer()
    original_story = "A girl enters a magical forest. She finds a glowing deer."

    story = composer.compose(original_story, target_duration_seconds=30)

    assert story == original_story


def test_story_composer_preserves_existing_multi_sentence_story() -> None:
    composer = StoryComposer()
    original_story = (
        "A princess opens a hidden gate. "
        "She finds a sleeping dragon. "
        "The dragon shows her a lost kingdom."
    )

    story = composer.compose(original_story, target_duration_seconds=20)

    assert story == original_story
