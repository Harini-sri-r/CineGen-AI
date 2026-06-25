"""Tests for cinematic prompt generation."""

from models.story import Scene
from services.prompt_generator import PromptGenerator


def test_generate_prompt_uses_keyword_templates_and_scene_text() -> None:
    generator = PromptGenerator()

    prompt = generator.generate_prompt(
        Scene(scene=1, description="A glowing deer stands near a waterfall")
    )

    assert prompt.scene == 1
    assert "glowing magical deer" in prompt.prompt
    assert "majestic waterfall" in prompt.prompt
    assert "a glowing deer stands near a waterfall" in prompt.prompt
    assert "cinematic composition" in prompt.prompt


def test_generate_prompts_preserves_scene_order() -> None:
    generator = PromptGenerator()
    scenes = [
        Scene(scene=1, description="A city street at night"),
        Scene(scene=2, description="A dragon above a mountain"),
    ]

    prompts = generator.generate_prompts(scenes)

    assert [prompt.scene for prompt in prompts] == [1, 2]
    assert "cinematic urban street" in prompts[0].prompt
    assert "mythic creature" in prompts[1].prompt
