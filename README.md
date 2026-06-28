# CineGen AI

Generate cinematic scene prompts, images, narration, and MP4 videos from a
story or a short idea such as `princess story`.

The browser UI includes a video length control. Set it to `20`, `30`, or any
value from 10 to 120 seconds before generating.

## Hugging Face image generation

Set these values in `.env` to use Hugging Face Inference Providers:

```env
CINEGEN_IMAGE_PROVIDER=huggingface
HF_TOKEN=your_hugging_face_token
CINEGEN_HF_MODEL_ID=black-forest-labs/FLUX.1-schnell
CINEGEN_HF_PROVIDER=hf-inference
CINEGEN_IMAGE_FALLBACK_PROVIDERS=fal,pollinations,storyboard
CINEGEN_IMAGE_WIDTH=512
CINEGEN_IMAGE_HEIGHT=512
CINEGEN_INFERENCE_STEPS=25
CINEGEN_GUIDANCE_SCALE=7.0
```

`HF_TOKEN` must have permission to call Hugging Face Inference Providers. If the
token exists but lacks that access, the API returns `403 Forbidden` and CineGen
falls back to the next configured image provider.

Short ideas and one-sentence stories are expanded into multiple scenes, so a
normal generation produces at least 3 scene images.

If all hosted image providers fail or their credentials are missing, `storyboard`
renders local illustrated PNG panels so the project still returns visible scene
images.

Run the API:

```powershell
pip install -r requirements.txt
python -m uvicorn app:app --reload --port 8001
```

Open `index.html` in your browser and generate a story.
