from diffusers import StableDiffusionPipeline

pipe = StableDiffusionPipeline.from_pretrained(
    "runwayml/stable-diffusion-v1-5"
)

image = pipe(
    "A beautiful futuristic city at sunset",
    num_inference_steps=6,
    height=192,
    width=192
).images[0]

image.save("test_image.png")

print("Image Generated Successfully")