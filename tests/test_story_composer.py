"""Tests for short idea story composition."""

from services.story_composer import StoryComposer


def test_story_composer_expands_short_idea_for_target_duration() -> None:
    composer = StoryComposer()

    story = composer.compose("princess story", target_duration_seconds=30)

    assert "a princess" in story
    assert story.count(".") == 5
    assert story.startswith("At the beginning")
    assert story.endswith("the world feels whole and hopeful again.")


def test_story_composer_keeps_ending_for_short_video() -> None:
    composer = StoryComposer()

    story = composer.compose("lost robot", target_duration_seconds=20)

    assert story.count(".") == 4
    assert "final challenge" in story
    assert story.endswith("the world feels whole and hopeful again.")


def test_story_composer_preserves_existing_multi_sentence_story() -> None:
    composer = StoryComposer()
    original_story = (
        "A princess opens a hidden gate. "
        "She finds a sleeping dragon. "
        "The dragon shows her a lost kingdom."
    )

    story = composer.compose(original_story, target_duration_seconds=20)

    assert story == original_story
