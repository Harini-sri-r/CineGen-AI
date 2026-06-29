"""Tests for cinematic prompt generation."""

from models.story import Scene
from services.prompt_generator import PromptGenerator


def test_generate_prompt_uses_keyword_templates_and_scene_text() -> None:
    generator = PromptGenerator()

    prompt = generator.generate_prompt(
        Scene(scene=1, description="A glowing deer stands near a waterfall")
    )

    assert prompt.scene == 1
    assert "cute glowing deer" in prompt.prompt
    assert "sparkling storybook waterfall" in prompt.prompt
    assert "Background: sparkling waterfall pool" in prompt.prompt
    assert "Scene must clearly show: A glowing deer stands near a waterfall" in prompt.prompt
    assert "children's animated storybook illustration" in prompt.prompt
    assert "2D cartoon style for kids" in prompt.prompt
    assert "clear subject focus" in prompt.prompt
    assert "gentle magical atmosphere" not in prompt.prompt
    assert "photorealistic cinematic still" not in prompt.prompt


def test_generate_prompts_preserves_scene_order() -> None:
    generator = PromptGenerator()
    scenes = [
        Scene(scene=1, description="A city street at night"),
        Scene(scene=2, description="A dragon above a mountain"),
    ]

    prompts = generator.generate_prompts(scenes)

    assert [prompt.scene for prompt in prompts] == [1, 2]
    assert "Background: cheerful town street" in prompts[0].prompt
    assert "colorful cartoon town street" in prompts[0].prompt
    assert "Background: rounded mountain landscape" in prompts[1].prompt
    assert "friendly cartoon dragon" in prompts[1].prompt


def test_generate_prompts_carries_forest_and_character_context() -> None:
    generator = PromptGenerator()
    scenes = [
        Scene(scene=1, description="A girl enters a forest"),
        Scene(scene=2, description="She saw a beautiful flower"),
    ]

    prompts = generator.generate_prompts(scenes)

    assert "Scene must clearly show: A girl enters a forest" in prompts[0].prompt
    assert "child character with simple expressive cartoon features" in prompts[0].prompt
    assert "Scene must clearly show: She saw a beautiful flower" in prompts[1].prompt
    assert "Background: inside the same natural forest" in prompts[1].prompt
    assert "Setting: inside the same natural forest" in prompts[1].prompt
    assert "Main character: the same young girl from the story" in prompts[1].prompt
    assert "single beautiful cartoon flower as the clear focal point" in prompts[1].prompt
    assert "no unrelated modern city streets, cars, or office buildings" in prompts[1].prompt


def test_generate_prompts_adds_story_specific_background_for_vague_followup() -> None:
    generator = PromptGenerator()
    scenes = [
        Scene(scene=1, description="A lost robot wakes in a repair workshop"),
        Scene(scene=2, description="It shares a battery light with a friend"),
    ]

    prompts = generator.generate_prompts(scenes)

    assert "Background: bright future workshop" in prompts[0].prompt
    assert "Background: inside the same bright future workshop" in prompts[1].prompt
    assert "friendly rounded robot character" in prompts[0].prompt
