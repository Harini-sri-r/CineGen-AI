"""Scene extraction service for CineGen AI."""

import re

from models.story import Scene


class SceneGenerator:
    """Extract numbered scenes from story text.

    The current implementation uses lightweight sentence splitting. The public
    method is intentionally narrow so a future LLM-backed extractor can replace
    the internals without changing API routes or response models.
    """

    _sentence_boundary_pattern = re.compile(r"(?<=[.!?])\s+|\n+")

    def extract_scenes(self, story: str) -> list[Scene]:
        """Split a story into ordered, non-empty scene descriptions."""
        sentences = self._split_into_sentences(story)
        cleaned_sentences: list[str] = []

        for sentence in sentences:
            cleaned_sentence = self._clean_sentence(sentence)
            if cleaned_sentence:
                cleaned_sentences.append(cleaned_sentence)

        return [
            Scene(scene=index, description=description)
            for index, description in enumerate(cleaned_sentences, start=1)
        ]

    def _split_into_sentences(self, story: str) -> list[str]:
        """Split story text by basic sentence boundaries and line breaks."""
        return self._sentence_boundary_pattern.split(story)

    def _clean_sentence(self, sentence: str) -> str:
        """Normalize whitespace and trim trailing sentence punctuation."""
        normalized = re.sub(r"\s+", " ", sentence).strip()
        return normalized.rstrip(".!?;:").strip()
