"""Cinematic prompt generation service for CineGen AI."""

from collections.abc import Iterable

from models.story import Prompt, Scene


class PromptGenerator:
    """Generate cinematic image prompts from extracted scenes."""

    _keyword_templates: dict[str, tuple[str, ...]] = {
        "forest": ("cinematic fantasy forest", "magical lighting"),
        "woods": ("cinematic fantasy forest", "magical lighting"),
        "jungle": ("lush cinematic jungle", "misty atmosphere"),
        "city": ("cinematic cityscape", "neon lights"),
        "street": ("cinematic urban street", "dramatic reflections"),
        "waterfall": ("majestic waterfall", "cinematic view"),
        "river": ("flowing river landscape", "soft natural light"),
        "ocean": ("vast ocean vista", "epic cinematic scale"),
        "mountain": ("towering mountain landscape", "wide angle view"),
        "castle": ("ancient castle", "epic fantasy atmosphere"),
        "deer": ("glowing magical deer", "realistic wildlife", "ultra detailed"),
        "animal": ("realistic wildlife", "ultra detailed"),
        "wolf": ("realistic wildlife", "ultra detailed"),
        "bird": ("realistic wildlife", "ultra detailed"),
        "dragon": ("mythic creature", "epic fantasy lighting"),
        "magic": ("enchanted atmosphere", "volumetric lighting"),
        "magical": ("enchanted atmosphere", "volumetric lighting"),
        "glowing": ("ethereal glow", "volumetric lighting"),
        "night": ("moonlit scene", "high contrast cinematic lighting"),
        "sunset": ("golden hour lighting", "cinematic color grading"),
    }
    _default_style: tuple[str, ...] = (
        "cinematic composition",
        "dramatic lighting",
        "ultra realistic",
        "4k movie scene",
    )

    def generate_prompts(self, scenes: Iterable[Scene]) -> list[Prompt]:
        """Generate one cinematic prompt per scene."""
        return [self.generate_prompt(scene) for scene in scenes]

    def generate_prompt(self, scene: Scene) -> Prompt:
        """Generate a cinematic prompt for a single scene."""
        prompt_parts = self._match_templates(scene.description)
        prompt_parts.append(scene.description.lower())
        prompt_parts.extend(self._default_style)

        return Prompt(
            scene=scene.scene,
            prompt=self._deduplicate_and_join(prompt_parts),
        )

    def _match_templates(self, description: str) -> list[str]:
        """Return template fragments that match keywords in the description."""
        lowered_description = description.lower()
        matched_parts: list[str] = []

        for keyword, template_parts in self._keyword_templates.items():
            if keyword in lowered_description:
                matched_parts.extend(template_parts)

        return matched_parts

    def _deduplicate_and_join(self, prompt_parts: Iterable[str]) -> str:
        """Join prompt fragments while preserving order and removing duplicates."""
        seen: set[str] = set()
        unique_parts: list[str] = []

        for part in prompt_parts:
            normalized = part.strip()
            normalized_key = normalized.lower()
            if normalized and normalized_key not in seen:
                seen.add(normalized_key)
                unique_parts.append(normalized)

        return ", ".join(unique_parts)
