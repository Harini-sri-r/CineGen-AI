"""Tests for story request validation."""

import pytest
from pydantic import ValidationError

from models.story import MIN_STORY_LENGTH, StoryRequest


def test_story_request_trims_valid_story() -> None:
    request = StoryRequest(story="  princess story  ")

    assert request.story == "princess story"
    assert request.text_only is False
    assert request.target_duration_seconds == 30


@pytest.mark.parametrize("story", ["", "   ", "hi"])
def test_story_request_rejects_empty_or_short_story(story: str) -> None:
    with pytest.raises(ValidationError):
        StoryRequest(story=story)


def test_minimum_story_length_constant_matches_contract() -> None:
    assert MIN_STORY_LENGTH == 3
