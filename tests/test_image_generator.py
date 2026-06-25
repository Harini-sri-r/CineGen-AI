"""Tests for image generation helpers."""

import base64
from contextlib import nullcontext
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from models.story import Prompt
from services.image_generator import ImageGenerator


class FakeTorch:
    """Minimal torch stand-in for image generator unit tests."""

    float16 = "float16"
    float32 = "float32"

    class cuda:
        @staticmethod
        def is_available() -> bool:
            return False

    @staticmethod
    def set_num_threads(thread_count: int) -> None:
        assert thread_count == 4

    @staticmethod
    def inference_mode():
        return nullcontext()


class FakeStableDiffusionPipeline:
    """Minimal diffusers pipeline stand-in for load/cache tests."""

    load_count = 0

    @classmethod
    def from_pretrained(cls, model_id: str, torch_dtype: str):
        cls.load_count += 1
        assert model_id == "runwayml/stable-diffusion-v1-5"
        assert torch_dtype == "float32"
        return cls()

    def to(self, device: str):
        assert device == "cpu"
        return self

    def enable_attention_slicing(self) -> None:
        pass

    def enable_vae_slicing(self) -> None:
        pass

    def enable_vae_tiling(self) -> None:
        pass

    def set_progress_bar_config(self, disable: bool) -> None:
        assert disable is True


class TimeoutPipeline:
    """Pipeline stand-in that trips the per-step timeout callback."""

    def __call__(self, **kwargs):
        kwargs["callback_on_step_end"](self, 0, None, {})
        return SimpleNamespace(images=[])


class FakeHttpResponse:
    """Tiny urlopen response stand-in for hosted image provider tests."""

    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return self.body


def test_image_generator_keeps_constructor_defaults_until_device_detection(tmp_path) -> None:
    generator = ImageGenerator(output_dir=tmp_path)

    assert generator.provider == "pollinations"
    assert generator.image_width == 256
    assert generator.image_height == 256
    assert generator.num_inference_steps == 10


def test_cpu_mode_applies_lightweight_settings_and_caches_model(
    tmp_path,
    monkeypatch,
) -> None:
    FakeStableDiffusionPipeline.load_count = 0
    monkeypatch.setitem(__import__("sys").modules, "torch", FakeTorch)
    monkeypatch.setitem(
        __import__("sys").modules,
        "diffusers",
        SimpleNamespace(StableDiffusionPipeline=FakeStableDiffusionPipeline),
    )
    generator = ImageGenerator(
        image_provider="stable-diffusion",
        output_dir=tmp_path,
        image_width=512,
        image_height=512,
        num_inference_steps=30,
        guidance_scale=9.0,
    )

    first_pipeline = generator.load_model()
    second_pipeline = generator.load_model()

    assert first_pipeline is second_pipeline
    assert FakeStableDiffusionPipeline.load_count == 1
    assert generator.device == "cpu"
    assert generator.image_width == 192
    assert generator.image_height == 192
    assert generator.num_inference_steps == 6
    assert generator.guidance_scale == 5.5


def test_timeout_saves_placeholder_and_continues(tmp_path, monkeypatch) -> None:
    import services.image_generator as image_generator_module

    times = iter([0.0, 121.0, 121.0])
    monkeypatch.setattr(
        image_generator_module,
        "perf_counter",
        lambda: next(times, 121.0),
    )
    generator = ImageGenerator(
        image_provider="stable-diffusion",
        output_dir=tmp_path,
        image_width=64,
        image_height=64,
        generation_timeout_seconds=90,
    )
    generator.pipeline = TimeoutPipeline()
    generator._torch = FakeTorch()
    generator.device = "cpu"

    images = generator.generate_images([Prompt(scene=1, prompt="slow scene")])

    assert images[0].status == "failed"
    assert "timed out" in (images[0].error or "")
    assert images[0].image_path is not None
    assert Path(images[0].image_path).exists()


def test_failed_images_save_scene_placeholder(tmp_path) -> None:
    generator = ImageGenerator(output_dir=tmp_path, image_width=64, image_height=64)

    images = generator.build_failed_images(
        [Prompt(scene=1, prompt="cinematic failed scene")],
        RuntimeError("pipeline exploded"),
    )

    assert images[0].scene == 1
    assert images[0].status == "failed"
    assert images[0].image_path is not None
    assert Path(images[0].image_path).name == "scene_1.png"
    assert Path(images[0].image_path).exists()


def test_single_image_generation_fallback_saves_placeholder(tmp_path) -> None:
    generator = ImageGenerator(output_dir=tmp_path, image_width=64, image_height=64)

    image = generator.generate_image_with_fallback("", 1)

    assert image.status == "failed"
    assert image.image_path is not None
    assert Path(image.image_path).exists()


def test_fal_provider_generates_and_saves_returned_image(
    tmp_path,
    monkeypatch,
) -> None:
    from PIL import Image

    calls: list[tuple[str, dict]] = []
    image_buffer = BytesIO()
    Image.new("RGB", (8, 8), color=(20, 120, 220)).save(image_buffer, format="PNG")
    encoded_image = base64.b64encode(image_buffer.getvalue()).decode("ascii")

    class FakeFalClient:
        @staticmethod
        def subscribe(model_id: str, arguments: dict):
            calls.append((model_id, arguments))
            return {
                "images": [
                    {
                        "url": f"data:image/png;base64,{encoded_image}",
                        "content_type": "image/png",
                    }
                ],
                "prompt": arguments["prompt"],
            }

    monkeypatch.setenv("FAL_KEY", "test-fal-key")
    monkeypatch.setitem(__import__("sys").modules, "fal_client", FakeFalClient)
    generator = ImageGenerator(image_provider="fal", output_dir=tmp_path)

    image = generator.generate_image("cinematic waterfall at dawn", 1)

    assert generator.provider == "fal"
    assert image.status == "success"
    assert image.image_path is not None
    assert Path(image.image_path).exists()
    assert calls == [
        (
            "fal-ai/flux/schnell",
            {
                "prompt": "cinematic waterfall at dawn",
                "image_size": "landscape_16_9",
                "num_inference_steps": 4,
                "guidance_scale": 3.5,
                "num_images": 1,
                "enable_safety_checker": True,
                "output_format": "png",
                "sync_mode": True,
                "acceleration": "regular",
            },
        )
    ]


def test_fal_missing_api_key_saves_placeholder(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("FAL_KEY", raising=False)
    monkeypatch.delenv("CINEGEN_FAL_KEY", raising=False)
    generator = ImageGenerator(
        image_provider="fal",
        output_dir=tmp_path,
        image_width=64,
        image_height=64,
    )

    image = generator.generate_image_with_fallback("cinematic forest temple", 1)

    assert image.status == "failed"
    assert "FAL_KEY" in (image.error or "")
    assert image.image_path is not None
    assert Path(image.image_path).exists()


def test_pollinations_provider_generates_and_saves_returned_image(
    tmp_path,
    monkeypatch,
) -> None:
    import services.image_generator as image_generator_module
    from PIL import Image

    captured_requests = []
    image_buffer = BytesIO()
    Image.new("RGB", (8, 8), color=(120, 40, 220)).save(image_buffer, format="PNG")
    encoded_image = base64.b64encode(image_buffer.getvalue()).decode("ascii")
    response_body = (
        '{"created":1,"data":[{"b64_json":"' + encoded_image + '"}]}'
    ).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured_requests.append((request, timeout))
        return FakeHttpResponse(response_body)

    monkeypatch.setenv("POLLINATIONS_KEY", "test-pollinations-key")
    monkeypatch.setattr(image_generator_module, "urlopen", fake_urlopen)
    generator = ImageGenerator(output_dir=tmp_path)

    image = generator.generate_image("cinematic moonlit castle", 1)

    assert generator.provider == "pollinations"
    assert image.status == "success"
    assert image.image_path is not None
    assert Path(image.image_path).exists()
    assert len(captured_requests) == 1
    request, timeout = captured_requests[0]
    assert request.full_url == "https://gen.pollinations.ai/v1/images/generations"
    assert timeout == 180.0
    assert request.headers["Authorization"] == "Bearer test-pollinations-key"
    assert b'"model": "zimage"' in request.data
    assert b'"response_format": "b64_json"' in request.data


def test_pollinations_missing_api_key_saves_placeholder(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("POLLINATIONS_KEY", raising=False)
    monkeypatch.delenv("CINEGEN_POLLINATIONS_KEY", raising=False)
    generator = ImageGenerator(output_dir=tmp_path, image_width=64, image_height=64)

    image = generator.generate_image_with_fallback("cinematic desert road", 1)

    assert image.status == "failed"
    assert "POLLINATIONS_KEY" in (image.error or "")
    assert image.image_path is not None
    assert Path(image.image_path).exists()
