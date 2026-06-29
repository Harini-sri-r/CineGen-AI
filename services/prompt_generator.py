"""Children's story prompt generation service for CineGen AI."""

from collections.abc import Iterable
import re

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
        "robot": ("friendly rounded robot character", "soft glowing technology details"),
        "astronaut": ("friendly astronaut suit", "gentle space adventure design"),
        "pirate": ("friendly storybook pirate design", "wooden ship adventure details"),
        "spaceship": ("rounded friendly spaceship", "soft glowing windows"),
        "school": ("cheerful school day details",),
        "shop": ("cozy small shop details",),
        "ice cream": ("bright ice cream treat as a clear prop",),
        "garden": ("colorful garden flowers", "leafy natural details"),
        "space": ("soft starry sky", "gentle cosmic wonder"),
        "desert": ("warm sandy dunes", "wide open storybook landscape"),
        "cave": ("sparkling cave crystals", "soft safe shadows"),
    }
    _background_templates: tuple[tuple[tuple[str, ...], str], ...] = (
        (
            ("forest", "woods"),
            "Background: layered storybook forest with mossy ground, rounded trees, and leaf-filtered light",
        ),
        (
            ("jungle",),
            "Background: bright jungle clearing with oversized leaves, vines, and warm dappled light",
        ),
        (
            ("castle", "kingdom", "princess", "prince", "queen", "wizard"),
            "Background: fairy-tale castle grounds with towers, banners, garden paths, and distant hills",
        ),
        (
            ("waterfall",),
            "Background: sparkling waterfall pool with smooth stones, mist, and soft blue water",
        ),
        (
            ("river", "lake"),
            "Background: winding storybook waterway with grassy banks, stepping stones, and reflections",
        ),
        (
            ("ocean", "sea", "beach", "island", "mermaid"),
            "Background: sunny seaside setting with waves, shells, warm sand, and a friendly horizon",
        ),
        (
            ("ship", "pirate", "harbor"),
            "Background: wooden ship deck and bright harbor water with sails, ropes, and a clear sky",
        ),
        (
            ("mountain", "snow"),
            "Background: rounded mountain landscape with soft clouds, safe paths, and painted sky",
        ),
        (
            ("city", "street", "town", "road"),
            "Background: cheerful town street with colorful storefronts, crosswalks, and rounded buildings",
        ),
        (
            ("shop", "ice cream"),
            "Background: cozy small shop exterior with striped awning, window display, and sidewalk details",
        ),
        (
            ("school", "classroom"),
            "Background: bright school setting with chalk drawings, cubbies, books, and sunny windows",
        ),
        (
            ("home", "house", "bedroom", "kitchen", "room"),
            "Background: cozy home interior with warm window light, simple furniture, and story props",
        ),
        (
            ("garden", "meadow", "farm"),
            "Background: colorful garden meadow with flowers, rounded bushes, and soft sunlight",
        ),
        (
            ("space", "spaceship", "astronaut", "planet", "rocket", "star"),
            "Background: friendly outer-space scene with stars, planets, spaceship windows, and soft cosmic light",
        ),
        (
            ("robot", "machine", "future", "lab", "workshop"),
            "Background: bright future workshop with friendly machines, glowing panels, tools, and tidy shelves",
        ),
        (
            ("desert", "sand", "dune"),
            "Background: warm desert landscape with rounded dunes, gentle sun, and a clear safe path",
        ),
        (
            ("cave", "underground"),
            "Background: sparkling cave with rounded stone walls, crystals, and soft safe shadows",
        ),
        (
            ("library", "museum"),
            "Background: quiet discovery room with shelves, display cases, ladders, and warm reading light",
        ),
        (
            ("park", "playground"),
            "Background: friendly park with benches, trees, play equipment, and open grass",
        ),
    )
    _default_style: tuple[str, ...] = (
        "children's animated storybook illustration",
        "2D cartoon style for kids",
        "bright cheerful colors",
        "soft rounded shapes",
        "simple expressive characters",
        "story-specific background details",
        "warm child-safe mood",
        "clear subject focus",
        "safe and wholesome",
    )
    _location_contexts: dict[str, str] = {
        "forest": "inside the same natural forest",
        "woods": "inside the same natural forest",
        "jungle": "inside the same lush jungle",
        "city": "in the same city setting",
        "town": "in the same cheerful town",
        "street": "on the same street",
        "shop": "outside the same cozy small shop",
        "school": "at the same bright school",
        "home": "inside the same cozy home",
        "house": "inside the same cozy home",
        "kitchen": "inside the same warm kitchen",
        "bedroom": "inside the same bedroom",
        "waterfall": "near the same waterfall",
        "river": "near the same river",
        "lake": "beside the same lake",
        "ocean": "beside the same ocean",
        "sea": "beside the same ocean",
        "beach": "on the same beach",
        "island": "on the same island",
        "ship": "aboard the same wooden ship",
        "space": "in the same friendly outer-space setting",
        "spaceship": "inside the same rounded spaceship",
        "planet": "on the same colorful planet",
        "robot": "inside the same bright future workshop",
        "workshop": "inside the same bright workshop",
        "lab": "inside the same friendly lab",
        "mountain": "near the same mountain landscape",
        "desert": "in the same warm desert",
        "garden": "inside the same colorful garden",
        "meadow": "inside the same meadow",
        "cave": "inside the same sparkling cave",
        "library": "inside the same quiet library",
        "museum": "inside the same museum hall",
        "park": "inside the same friendly park",
        "castle": "near the same ancient castle",
    }
    _genre_setting_contexts: dict[str, str] = {
        "princess": "around a fairy-tale castle and village with towers, banners, and garden paths",
        "prince": "around a fairy-tale castle and village with towers, banners, and garden paths",
        "queen": "around a fairy-tale castle and village with towers, banners, and garden paths",
        "wizard": "around a fairy-tale castle and village with towers, banners, and garden paths",
        "dragon": "near rounded mountains and a safe storybook cave",
        "robot": "inside a bright future workshop with friendly machines and glowing panels",
        "astronaut": "inside a friendly spaceship among stars and colorful planets",
        "spaceship": "inside a friendly spaceship among stars and colorful planets",
        "pirate": "aboard a wooden ship near a sunny island harbor",
        "mermaid": "beside a sunny seaside cove with shells and blue water",
        "detective": "inside a quiet library mystery room with shelves and warm lamplight",
    }
    _character_contexts: dict[str, str] = {
        "girl": "the same young girl from the story",
        "boy": "the same young boy from the story",
        "woman": "the same woman from the story",
        "man": "the same man from the story",
    }
    _pronouns: tuple[str, ...] = ("she", "her", "he", "him", "they", "them")
    _urban_terms: tuple[str, ...] = (
        "building",
        "car",
        "city",
        "road",
        "school",
        "shop",
        "street",
        "town",
    )
    _indoor_terms: tuple[str, ...] = (
        "bedroom",
        "classroom",
        "home",
        "house",
        "inside",
        "kitchen",
        "lab",
        "library",
        "museum",
        "room",
        "spaceship",
        "workshop",
    )

    def generate_prompts(self, scenes: Iterable[Scene]) -> list[Prompt]:
        """Generate one cinematic prompt per scene."""
        scene_list = list(scenes)
        prompts: list[Prompt] = []
        story_setting_context = self._best_story_setting_context(scene_list)
        location_context = ""
        character_context = ""

        for scene in scene_list:
            prompt = self.generate_prompt(
                scene,
                location_context=location_context,
                character_context=character_context,
                story_setting_context=story_setting_context,
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
        story_setting_context: str = "",
    ) -> Prompt:
        """Generate a child-friendly prompt for a single scene."""
        prompt_parts = [f"Scene must clearly show: {self._clean_description(scene.description)}"]
        prompt_parts.extend(
            self._background_parts(
                scene.description,
                location_context=location_context,
                story_setting_context=story_setting_context,
            )
        )
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
            if self._contains_keyword(lowered_description, keyword):
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
            constraints.append("no unrelated modern city streets, cars, or office buildings")

        if not any(term in lowered_description for term in self._indoor_terms):
            constraints.append("no unrelated indoor rooms")

        return constraints

    def _latest_location_context(self, description: str, current_context: str) -> str:
        """Return the latest explicit location context from a scene."""
        lowered_description = description.lower()
        for keyword, context in self._location_contexts.items():
            if self._contains_keyword(lowered_description, keyword):
                return context

        return current_context

    def _latest_character_context(self, description: str, current_context: str) -> str:
        """Return the latest explicit character context from a scene."""
        lowered_description = description.lower()
        for keyword, context in self._character_contexts.items():
            if self._contains_keyword(lowered_description, keyword):
                return context

        return current_context

    def _has_location_context(self, lowered_description: str) -> bool:
        """Return whether a scene already includes a known setting."""
        return any(
            self._contains_keyword(lowered_description, keyword)
            for keyword in self._location_contexts
        )

    def _uses_pronoun(self, lowered_description: str) -> bool:
        """Return whether a scene likely refers to a previous character."""
        words = set(lowered_description.replace(".", " ").replace(",", " ").split())
        return any(pronoun in words for pronoun in self._pronouns)

    def _clean_description(self, description: str) -> str:
        """Normalize scene text for use as the primary visual instruction."""
        return " ".join(description.split()).rstrip(".!?;:").strip()

    def _background_parts(
        self,
        description: str,
        location_context: str,
        story_setting_context: str,
    ) -> list[str]:
        """Return an explicit background instruction for the scene."""
        matched_background = self._match_background_template(description)
        if matched_background:
            return [matched_background]

        if location_context:
            return [f"Background: {location_context} with visible props from the current scene"]

        if story_setting_context:
            return [f"Background: {story_setting_context}"]

        return [
            "Background: a concrete story location with visible props from the scene, not a plain generic backdrop"
        ]

    def _best_story_setting_context(self, scenes: Iterable[Scene]) -> str:
        """Infer a useful setting from the full scene list."""
        combined_description = " ".join(scene.description for scene in scenes)
        matched_context = self._match_location_context(combined_description)
        if matched_context:
            return matched_context

        lowered_description = combined_description.lower()
        for keyword, context in self._genre_setting_contexts.items():
            if self._contains_keyword(lowered_description, keyword):
                return context

        return ""

    def _match_background_template(self, description: str) -> str:
        """Return the first concrete background that matches a scene."""
        lowered_description = description.lower()
        for keywords, background in self._background_templates:
            if any(self._contains_keyword(lowered_description, keyword) for keyword in keywords):
                return background

        return ""

    def _match_location_context(self, description: str) -> str:
        """Return the first reusable setting context that matches text."""
        lowered_description = description.lower()
        for keyword, context in self._location_contexts.items():
            if self._contains_keyword(lowered_description, keyword):
                return context

        return ""

    def _contains_keyword(self, lowered_text: str, keyword: str) -> bool:
        """Match whole words and simple phrases inside already-lowered text."""
        lowered_keyword = keyword.lower()
        if " " in lowered_keyword:
            return lowered_keyword in lowered_text

        return re.search(
            rf"(?<![a-z0-9]){re.escape(lowered_keyword)}(?![a-z0-9])",
            lowered_text,
        ) is not None
