"""Story composition helpers for short user ideas."""

from __future__ import annotations

import re

from models.story import DEFAULT_VIDEO_DURATION_SECONDS


class StoryComposer:
    """Expand short ideas into a scene-friendly story."""

    _sentence_boundary_pattern = re.compile(r"(?<=[.!?])\s+|\n+")
    _trailing_request_words = re.compile(
        r"\b(story|video|movie|prompt|scene|scenes|please|make|create|generate)\b",
        re.IGNORECASE,
    )
    _opening_template = (
        "At the beginning, {subject} lives in a familiar world with a dream "
        "that feels just out of reach."
    )
    _middle_templates: tuple[str, ...] = (
        "A surprising call to adventure pulls {subject} away from safety and gives the journey a clear purpose.",
        "{subject_title} follows the first clue into a vivid new place where wonder and danger grow together.",
        "A setback forces {subject} to choose between the easy path and doing what is right.",
        "At the darkest moment, {subject} discovers courage and compassion that were hidden inside all along.",
        "{subject_title} faces the final challenge and changes the outcome with a brave choice.",
        "The victory protects something precious, and {subject} understands what the journey was really about.",
    )
    _ending_template = (
        "In the final quiet moment, {subject} returns changed, and the world "
        "feels whole and hopeful again."
    )
    _middle_template_indexes_by_count: dict[int, tuple[int, ...]] = {
        1: (4,),
        2: (0, 4),
        3: (0, 2, 4),
        4: (0, 1, 3, 4),
        5: (0, 1, 2, 3, 4),
    }

    def compose(
        self,
        user_text: str,
        target_duration_seconds: int | None = None,
        minimum_scene_count: int = 3,
    ) -> str:
        """Return story text ready for scene extraction."""
        cleaned_text = self._clean_text(user_text)
        if not cleaned_text:
            return ""

        if self._looks_like_story(cleaned_text, minimum_scene_count):
            return cleaned_text

        subject = self._build_subject(cleaned_text)
        scene_count = max(
            minimum_scene_count,
            self._target_scene_count(target_duration_seconds),
        )
        return " ".join(
            template.format(
                subject=subject,
                subject_title=self._sentence_case(subject),
            )
            for template in self._select_templates(scene_count)
        )

    def _select_templates(self, scene_count: int) -> tuple[str, ...]:
        """Return story templates with a beginning and ending every time."""
        if scene_count <= 2:
            return (self._opening_template, self._ending_template)

        middle_count = scene_count - 2
        if middle_count >= len(self._middle_templates):
            return (
                self._opening_template,
                *self._middle_templates,
                self._ending_template,
            )

        indexes = self._middle_template_indexes_by_count[middle_count]
        selected_middle = tuple(self._middle_templates[index] for index in indexes)
        return (self._opening_template, *selected_middle, self._ending_template)

    def _looks_like_story(self, text: str, minimum_scene_count: int) -> bool:
        """Return true when input already has enough story structure."""
        sentences = [
            sentence.strip()
            for sentence in self._sentence_boundary_pattern.split(text)
            if sentence.strip()
        ]
        word_count = len(text.split())
        return len(sentences) >= minimum_scene_count and word_count >= 8

    def _target_scene_count(self, target_duration_seconds: int | None) -> int:
        """Choose enough scenes for a readable video at the requested length."""
        duration = target_duration_seconds or DEFAULT_VIDEO_DURATION_SECONDS
        if duration <= 20:
            return 4
        if duration <= 35:
            return 5
        if duration <= 50:
            return 6
        return 7

    def _build_subject(self, text: str) -> str:
        """Turn request-like text into a simple story subject."""
        subject = self._trailing_request_words.sub(" ", text)
        subject = re.sub(r"[.!?;:]+", " ", subject)
        subject = re.sub(r"\s+", " ", subject).strip(" .,!?:;-")
        if not subject:
            subject = text.strip(" .,!?:;-")

        words = subject.split()
        if len(words) > 10:
            subject = " ".join(words[:10])

        if self._starts_with_determiner(subject):
            return subject

        return f"a {subject}"

    def _starts_with_determiner(self, text: str) -> bool:
        """Return true when a phrase already starts naturally."""
        first_word = text.split(maxsplit=1)[0].lower() if text.split() else ""
        return first_word in {"a", "an", "the", "my", "our", "his", "her", "their"}

    def _sentence_case(self, text: str) -> str:
        """Capitalize a phrase for sentence starts."""
        if not text:
            return text

        return f"{text[0].upper()}{text[1:]}"

    def _clean_text(self, text: str) -> str:
        """Normalize whitespace without changing the user's wording."""
        return " ".join(text.split()).strip()
