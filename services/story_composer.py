"""Story composition helpers for short user ideas."""

from __future__ import annotations

import hashlib
import re

from models.story import DEFAULT_VIDEO_DURATION_SECONDS


class StoryComposer:
    """Expand short ideas into a scene-friendly story."""

    _sentence_boundary_pattern = re.compile(r"(?<=[.!?])\s+|\n+")
    _trailing_request_words = re.compile(
        r"\b(story|video|movie|prompt|scene|scenes|please|make|create|generate)\b",
        re.IGNORECASE,
    )
    _article_exceptions = {"unicorn": "a", "user": "a", "hour": "an"}
    _character_nouns: tuple[str, ...] = (
        "astronaut",
        "boy",
        "cat",
        "child",
        "deer",
        "detective",
        "dog",
        "dragon",
        "fairy",
        "fox",
        "girl",
        "kid",
        "king",
        "mermaid",
        "pirate",
        "princess",
        "prince",
        "queen",
        "robot",
        "unicorn",
        "wizard",
    )
    _action_words: tuple[str, ...] = (
        "builds",
        "discovers",
        "eats",
        "enters",
        "explores",
        "finds",
        "flies",
        "follows",
        "helps",
        "is",
        "learns",
        "looks",
        "makes",
        "meets",
        "opens",
        "rides",
        "saves",
        "searches",
        "sees",
        "travels",
        "visits",
    )
    _profile_keywords: dict[str, tuple[str, ...]] = {
        "fantasy": (
            "castle",
            "dragon",
            "fairy",
            "kingdom",
            "magic",
            "magical",
            "princess",
            "prince",
            "queen",
            "unicorn",
            "wizard",
        ),
        "space": ("alien", "astronaut", "planet", "rocket", "space", "spaceship", "star"),
        "future": ("android", "machine", "robot", "tech", "future"),
        "ocean": ("beach", "island", "mermaid", "ocean", "pirate", "sea", "ship"),
        "nature": (
            "animal",
            "bird",
            "cat",
            "deer",
            "dog",
            "flower",
            "forest",
            "fox",
            "garden",
            "jungle",
            "tree",
            "woods",
        ),
        "mystery": ("clue", "detective", "hidden", "map", "mystery", "secret", "treasure"),
        "everyday": (
            "friend",
            "home",
            "ice cream",
            "park",
            "school",
            "shop",
            "street",
            "town",
        ),
    }
    _profiles: dict[str, dict[str, tuple[str, ...]]] = {
        "fantasy": {
            "settings": (
                "a lantern-lit castle garden",
                "a moonlit tower above a quiet kingdom",
                "a village square where painted banners flutter",
                "a crystal bridge over a sleepy moat",
            ),
            "discoveries": (
                "finds a silver key humming inside a teacup",
                "hears a tiny bell calling from behind a painted door",
                "spots a map glowing under a loose garden stone",
                "meets a shy cloud painter guarding a ribbon of starlight",
            ),
            "obstacles": (
                "a warm rain washes away the path before the next clue is safe",
                "the old tower door will only open for someone who shares a kindness",
                "a sleepy dragon blocks the bridge until its lost song is remembered",
                "the lanterns dim, and everyone must work by the last soft spark",
                "a mirror maze turns every shortcut into a longer lesson",
            ),
            "endings": (
                "the garden glows with new paths, and {subject} learns that kindness can guide a whole kingdom",
                "the forgotten tower opens, and {subject} brings its light back to every window",
                "the kingdom celebrates quietly, and {subject} keeps the little key as a promise to be brave",
            ),
        },
        "space": {
            "settings": (
                "a friendly spaceship circling a blue-green moon",
                "a glassy space station full of floating seedlings",
                "a comet dock where tiny service lights blink like fireflies",
                "a quiet planet with rings of peach-colored dust",
            ),
            "discoveries": (
                "catches a runaway star chart drifting past the window",
                "finds a blinking message tucked inside a moon rock",
                "hears a lonely satellite tapping a rhythm for help",
                "spots a trail of silver crumbs leading across the airlock",
            ),
            "obstacles": (
                "a meteor shower makes the safe route sparkle and disappear",
                "the engine hum turns shy and needs a gentle repair",
                "a lost signal echoes from two directions at once",
                "the moon dust rises so high that the landing lights vanish",
                "an empty fuel cell asks everyone to share what power they can",
            ),
            "endings": (
                "the stars line up into a bright road home, and {subject} understands how brave teamwork can be",
                "the little satellite sings again, and {subject} carries its message across the moon",
                "the station garden blooms in zero gravity, and {subject} saves the day with careful wonder",
            ),
        },
        "future": {
            "settings": (
                "a bright repair workshop under a humming city rail",
                "a neon recycling yard filled with friendly machines",
                "a rooftop garden where solar panels tilt toward sunrise",
                "a tiny maker lab with drawers of glowing spare parts",
            ),
            "discoveries": (
                "finds a trail of blue screws pointing toward a hidden signal",
                "hears a delivery drone beeping from inside a stack of boxes",
                "discovers a pocket-sized map blinking in a forgotten drawer",
                "notices one traffic light flashing a secret pattern",
            ),
            "obstacles": (
                "the power flickers just as the workshop doors slide shut",
                "a rainstorm turns the map into a maze of reflected lights",
                "a missing gear makes every helpful machine move too slowly",
                "the city clock starts counting down before the repair is finished",
                "the safest route is blocked, so a new path must be built from scraps",
            ),
            "endings": (
                "the workshop lights up again, and {subject} becomes the city helper everyone remembers",
                "the hidden signal turns into a song, and {subject} finds the way home with a new friend",
                "the rooftop garden opens at sunrise, and {subject} learns that small repairs can change a whole day",
            ),
        },
        "ocean": {
            "settings": (
                "a wooden ship beside a sparkling island lagoon",
                "a shell-covered beach where the tide leaves secret notes",
                "a coral cove glowing under clear blue water",
                "a tiny harbor with gulls circling over painted sails",
            ),
            "discoveries": (
                "finds a bottle map bobbing between silver waves",
                "hears a conch shell whisper from below the pier",
                "spots a trail of golden shells leading toward a hidden cove",
                "meets a nervous sea turtle carrying a broken compass",
            ),
            "obstacles": (
                "a playful wave scatters the map into three bright pieces",
                "the tide rises and covers the path across the rocks",
                "a fog bank hides the lighthouse just when it is needed most",
                "the old compass spins until someone tells the truth",
                "a tiny storm asks the crew to slow down and listen",
            ),
            "endings": (
                "the lighthouse shines across calm water, and {subject} shares the treasure with the whole harbor",
                "the hidden cove opens safely, and {subject} learns that the best treasure is a rescued friend",
                "the waves carry everyone home, and {subject} keeps one golden shell to remember the brave choice",
            ),
        },
        "nature": {
            "settings": (
                "a sun-dappled forest path filled with round green leaves",
                "a hillside garden buzzing softly with bees",
                "a quiet meadow beside a winding river",
                "a jungle clearing where bright flowers lean toward the light",
            ),
            "discoveries": (
                "finds a glowing seed tucked beneath a curled leaf",
                "hears a tiny bird calling from a branch too high to reach",
                "spots silver footprints crossing the moss",
                "meets a nervous little animal carrying a bent flower stem",
            ),
            "obstacles": (
                "the river rises and turns the stepping stones into little islands",
                "a gust of wind scatters the seed pods across the meadow",
                "the tallest tree creaks, asking for help before sunset",
                "a shadow covers the garden, and the flowers close their faces",
                "the path splits into loops until everyone listens for the quietest sound",
            ),
            "endings": (
                "the garden opens in color, and {subject} learns how gently one brave helper can change the forest",
                "the river settles into a bright song, and {subject} guides every friend safely home",
                "the meadow shines with new flowers, and {subject} promises to care for the small living things",
            ),
        },
        "mystery": {
            "settings": (
                "a quiet library with ladders and moonlit shelves",
                "a dusty attic above a friendly old theater",
                "a train station clock tower full of hidden drawers",
                "a museum hall where painted eyes seem to follow every clue",
            ),
            "discoveries": (
                "finds a folded note marked with a smiling compass",
                "hears a soft knock coming from inside an old picture frame",
                "spots a trail of blue chalk arrows under the tables",
                "discovers a tiny brass button that opens a secret drawer",
            ),
            "obstacles": (
                "the clue changes shape whenever it is rushed",
                "a locked cabinet asks for the name of someone who was kind",
                "the clock tower chimes early and hides the next hint",
                "two clues disagree until they are placed side by side",
                "the final drawer will open only when everyone shares what they noticed",
            ),
            "endings": (
                "the hidden room opens, and {subject} solves the mystery by noticing the smallest kindness",
                "the lost keepsake returns to its owner, and {subject} writes the answer in the library book",
                "the clock tower rings correctly again, and {subject} learns that patient questions light the way",
            ),
        },
        "everyday": {
            "settings": (
                "a cheerful neighborhood street beside a small shop",
                "a sunny school courtyard with chalk drawings on the ground",
                "a cozy kitchen where warm light spills across the table",
                "a busy park with benches, balloons, and friendly faces",
            ),
            "discoveries": (
                "finds a handmade note tucked under a bright red bench",
                "notices a small problem that everyone else is too busy to see",
                "meets a new friend carrying something important and fragile",
                "spots a trail of colorful stickers leading around the corner",
            ),
            "obstacles": (
                "a sudden spill turns the plan into a slippery puzzle",
                "the line gets long, and patience becomes the hardest part",
                "the wind scatters the decorations across the courtyard",
                "a shy friend needs help before the celebration can begin",
                "the missing piece is ordinary, tiny, and hidden in plain sight",
            ),
            "endings": (
                "the neighborhood feels brighter, and {subject} discovers that ordinary days can hold real adventures",
                "the small shop fills with laughter, and {subject} learns how one helpful choice can change the mood",
                "the courtyard celebration begins, and {subject} saves the day by paying attention",
            ),
        },
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
        return self._compose_from_profile(
            cleaned_text=cleaned_text,
            subject=subject,
            scene_count=scene_count,
        )

    def _compose_from_profile(
        self,
        cleaned_text: str,
        subject: str,
        scene_count: int,
    ) -> str:
        """Create a short, scene-ready story that fits the idea's theme."""
        profile = self._profiles[self._profile_key(cleaned_text)]
        seed = self._stable_seed(cleaned_text)
        subject_title = self._sentence_case(subject)
        setting = self._choice(profile["settings"], seed, 0)
        discovery = self._choice(profile["discoveries"], seed, 1)
        ending = self._choice(profile["endings"], seed, 2).format(subject=subject)

        story_sentences = [
            self._opening_sentence(
                cleaned_text=cleaned_text,
                subject=subject,
                setting=setting,
                seed=seed,
            ),
            f"{subject_title} {discovery}.",
        ]

        obstacle_count = max(0, scene_count - 3)
        for index, obstacle in enumerate(
            self._select_distinct(profile["obstacles"], seed, obstacle_count, offset=4),
        ):
            if index % 2:
                story_sentences.append(f"With a friend close by, {obstacle}.")
            else:
                story_sentences.append(f"Then {obstacle}.")

        story_sentences.append(f"By {self._choice(self._ending_times(), seed, 12)}, {ending}.")
        return " ".join(story_sentences[:scene_count])

    def _looks_like_story(self, text: str, minimum_scene_count: int) -> bool:
        """Return true when input already has enough story structure."""
        sentences = [
            sentence.strip()
            for sentence in self._sentence_boundary_pattern.split(text)
            if sentence.strip()
        ]
        word_count = len(text.split())
        return len(sentences) >= 2 and word_count >= 8

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
        subject = re.sub(r"\b(about|for|of|with)\b", " ", subject, flags=re.IGNORECASE)
        subject = re.sub(r"[.!?;:]+", " ", subject)
        subject = re.sub(r"\s+", " ", subject).strip(" .,!?:;-")
        if not subject:
            subject = text.strip(" .,!?:;-")

        known_subject = self._known_character_subject(subject)
        if known_subject:
            return known_subject

        words = subject.split()
        if len(words) > 10:
            subject = " ".join(words[:10])

        if self._starts_with_determiner(subject):
            return self._normalize_determiner_case(subject)

        return f"{self._article_for(subject)} {subject}"

    def _known_character_subject(self, text: str) -> str:
        """Prefer the main character over the whole request phrase."""
        words = text.split()
        lowered_words = [word.strip(" ,.!?;:").lower() for word in words]
        for index, word in enumerate(lowered_words):
            if word not in self._character_nouns:
                continue

            start = index
            if index > 0 and lowered_words[index - 1] not in self._action_words:
                start = index - 1

            phrase = " ".join(words[start : index + 1]).strip(" ,.!?;:")
            if start > 0 and lowered_words[start - 1] in {"a", "an", "the", "my", "our"}:
                phrase = f"{words[start - 1]} {phrase}"

            if self._starts_with_determiner(phrase):
                return self._normalize_determiner_case(phrase)

            return f"{self._article_for(phrase)} {phrase}"

        return ""

    def _starts_with_determiner(self, text: str) -> bool:
        """Return true when a phrase already starts naturally."""
        first_word = text.split(maxsplit=1)[0].lower() if text.split() else ""
        return first_word in {"a", "an", "the", "my", "our", "his", "her", "their"}

    def _article_for(self, phrase: str) -> str:
        """Return a rough English indefinite article for a phrase."""
        first_word = phrase.split(maxsplit=1)[0].lower() if phrase.split() else ""
        if first_word in self._article_exceptions:
            return self._article_exceptions[first_word]

        return "an" if first_word[:1] in {"a", "e", "i", "o", "u"} else "a"

    def _sentence_case(self, text: str) -> str:
        """Capitalize a phrase for sentence starts."""
        if not text:
            return text

        return f"{text[0].upper()}{text[1:]}"

    def _opening_sentence(
        self,
        cleaned_text: str,
        subject: str,
        setting: str,
        seed: int,
    ) -> str:
        """Use a user-provided event as the opening scene when possible."""
        premise = self._single_scene_premise(cleaned_text)
        if premise:
            return premise

        return (
            f"At {self._choice(self._opening_times(), seed, 3)}, "
            f"{subject} begins in {setting}."
        )

    def _single_scene_premise(self, text: str) -> str:
        """Return a one-sentence user premise that should stay visible."""
        sentences = [
            sentence.strip()
            for sentence in self._sentence_boundary_pattern.split(text)
            if sentence.strip()
        ]
        if len(sentences) != 1 or len(text.split()) < 5:
            return ""

        words = {word.strip(" ,.!?;:").lower() for word in text.split()}
        if not any(action_word in words for action_word in self._action_words):
            return ""

        return f"{sentences[0].rstrip('.!?;:')}."

    def _normalize_determiner_case(self, text: str) -> str:
        """Lowercase ordinary determiners so generated sentences read naturally."""
        words = text.split(maxsplit=1)
        if not words:
            return text

        if words[0].lower() in {"a", "an", "the"}:
            first_word = words[0].lower()
            return f"{first_word} {words[1]}" if len(words) > 1 else first_word

        return text

    def _profile_key(self, text: str) -> str:
        """Pick the strongest story profile for the submitted idea."""
        lowered_text = text.lower()
        for profile, keywords in self._profile_keywords.items():
            if any(keyword in lowered_text for keyword in keywords):
                return profile

        return "everyday"

    def _select_distinct(
        self,
        options: tuple[str, ...],
        seed: int,
        count: int,
        offset: int = 0,
    ) -> tuple[str, ...]:
        """Select deterministic options without repeating short stories."""
        if count <= 0:
            return ()

        start = (seed + offset) % len(options)
        step = seed % (len(options) - 1) + 1 if len(options) > 1 else 1
        selected: list[str] = []
        index = start

        while len(selected) < count:
            option = options[index % len(options)]
            if option not in selected:
                selected.append(option)
            index += step

        return tuple(selected)

    def _choice(self, options: tuple[str, ...], seed: int, offset: int) -> str:
        """Return a deterministic option for a generated idea."""
        return options[(seed + offset) % len(options)]

    def _stable_seed(self, text: str) -> int:
        """Create a stable seed so similar requests vary without randomness."""
        digest = hashlib.sha256(text.lower().encode("utf-8")).hexdigest()
        return int(digest[:8], 16)

    def _opening_times(self) -> tuple[str, ...]:
        """Return child-friendly opening time phrases."""
        return ("sunrise", "the first bell", "a bright morning", "moonrise")

    def _ending_times(self) -> tuple[str, ...]:
        """Return child-friendly ending time phrases."""
        return ("sunset", "starlight", "the final bell", "dinnertime")

    def _clean_text(self, text: str) -> str:
        """Normalize whitespace without changing the user's wording."""
        return " ".join(text.split()).strip()
