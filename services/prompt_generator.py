"""Children's story prompt generation service for CineGen AI."""

from collections.abc import Iterable

from models.story import Prompt, Scene


class PromptGenerator:
    """Generate child-friendly animated image prompts from extracted scenes."""

    _keyword_templates: dict[str, tuple[str, ...]] = {
        "forest": ("storybook forest with friendly rounded trees", "gentle magical light"),
        "woods": ("storybook forest with friendly rounded trees", "gentle magical light"),
        "jungle": ("bright cartoon jungle", "soft playful leaves"),
        "city": ("colorful cartoon town", "safe cheerful streets"),
        "street": ("colorful cartoon town street", "safe cheerful background"),
        "waterfall": ("sparkling storybook waterfall", "soft blue water"),
        "river": ("winding cartoon river", "soft blue water"),
        "ocean": ("wide friendly cartoon ocean", "playful waves"),
        "mountain": ("rounded storybook mountains", "soft painted sky"),
        "castle": ("storybook castle with rounded towers", "fairy tale colors"),
        "deer": ("cute glowing deer", "friendly animal design"),
        "animal": ("cute friendly animal design",),
        "wolf": ("gentle storybook wolf", "friendly animal design"),
        "bird": ("cute colorful bird", "friendly animal design"),
        "dragon": ("friendly cartoon dragon", "playful fantasy design"),
        "magic": ("sparkly gentle magic", "wonderful child-safe atmosphere"),
        "magical": ("sparkly gentle magic", "wonderful child-safe atmosphere"),
        "glowing": ("soft magical glow", "warm gentle light"),
        "night": ("cozy moonlit storybook scene", "soft low contrast lighting"),
        "sunset": ("warm pastel sunset", "storybook color palette"),
        "girl": ("child character with simple expressive cartoon features",),
        "boy": ("child character with simple expressive cartoon features",),
        "woman": ("kind adult character in cartoon style",),
        "man": ("kind adult character in cartoon style",),
        "flower": ("single beautiful cartoon flower as the clear focal point", "simple botanical shapes"),
    }
    _default_style: tuple[str, ...] = (
        "children's animated storybook illustration",
        "2D cartoon style for kids",
        "bright cheerful colors",
        "soft rounded shapes",
        "simple expressive characters",
        "gentle magical atmosphere",
        "clear subject focus",
        "safe and wholesome",
    )
    _location_contexts: dict[str, str] = {
        "forest": "inside the same natural forest",
        "woods": "inside the same natural forest",
        "jungle": "inside the same lush jungle",
        "city": "in the same city setting",
        "street": "on the same street",
        "waterfall": "near the same waterfall",
        "river": "near the same river",
        "ocean": "beside the same ocean",
        "mountain": "near the same mountain landscape",
        "castle": "near the same ancient castle",
    }
    _character_contexts: dict[str, str] = {
        "girl": "the same young girl from the story",
        "boy": "the same young boy from the story",
        "woman": "the same woman from the story",
        "man": "the same man from the story",
    }
    _pronouns: tuple[str, ...] = ("she", "her", "he", "him", "they", "them")
    _urban_terms: tuple[str, ...] = ("city", "street", "road", "building", "shop", "car")

    def generate_prompts(self, scenes: Iterable[Scene]) -> list[Prompt]:
        """Generate one cinematic prompt per scene."""
        prompts: list[Prompt] = []
        location_context = ""
        character_context = ""

        for scene in scenes:
            prompt = self.generate_prompt(
                scene,
                location_context=location_context,
                character_context=character_context,
            )
            prompts.append(prompt)

            location_context = self._latest_location_context(
                scene.description,
                location_context,
            )
            character_context = self._latest_character_context(
                scene.description,
                character_context,
            )

        return prompts

    def generate_prompt(
        self,
        scene: Scene,
        location_context: str = "",
        character_context: str = "",
    ) -> Prompt:
        """Generate a child-friendly prompt for a single scene."""
        prompt_parts = [f"Scene must clearly show: {self._clean_description(scene.description)}"]
        prompt_parts.extend(
            self._inherited_context_parts(
                scene.description,
                location_context=location_context,
                character_context=character_context,
            )
        )
        prompt_parts.extend(self._match_templates(scene.description))
        prompt_parts.extend(self._default_style)
        prompt_parts.extend(self._negative_constraints(scene.description))

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

    def _inherited_context_parts(
        self,
        description: str,
        location_context: str,
        character_context: str,
    ) -> list[str]:
        """Carry obvious story context into short follow-up scene prompts."""
        lowered_description = description.lower()
        context_parts: list[str] = []

        if location_context and not self._has_location_context(lowered_description):
            context_parts.append(f"Setting: {location_context}")

        if character_context and self._uses_pronoun(lowered_description):
            context_parts.append(f"Main character: {character_context}")

        return context_parts

    def _negative_constraints(self, description: str) -> list[str]:
        """Add concise constraints that reduce irrelevant visual drift."""
        lowered_description = description.lower()
        constraints = [
            "no photorealism",
            "no live action",
            "no real people",
            "no documentary photography",
            "no realistic street photo",
            "no abstract patterns",
            "no glitch artifacts",
            "no distorted subjects",
            "no scary imagery",
            "no violence",
            "no text",
            "no watermark",
        ]

        if not any(term in lowered_description for term in self._urban_terms):
            constraints.append("no city, buildings, roads, cars, or indoor rooms")

        return constraints

    def _latest_location_context(self, description: str, current_context: str) -> str:
        """Return the latest explicit location context from a scene."""
        lowered_description = description.lower()
        for keyword, context in self._location_contexts.items():
            if keyword in lowered_description:
                return context

        return current_context

    def _latest_character_context(self, description: str, current_context: str) -> str:
        """Return the latest explicit character context from a scene."""
        lowered_description = description.lower()
        for keyword, context in self._character_contexts.items():
            if keyword in lowered_description:
                return context

        return current_context

    def _has_location_context(self, lowered_description: str) -> bool:
        """Return whether a scene already includes a known setting."""
        return any(keyword in lowered_description for keyword in self._location_contexts)

    def _uses_pronoun(self, lowered_description: str) -> bool:
        """Return whether a scene likely refers to a previous character."""
        words = set(lowered_description.replace(".", " ").replace(",", " ").split())
        return any(pronoun in words for pronoun in self._pronouns)

    def _clean_description(self, description: str) -> str:
        """Normalize scene text for use as the primary visual instruction."""
        return " ".join(description.split()).rstrip(".!?;:").strip()
