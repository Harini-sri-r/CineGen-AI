"""FastAPI application entrypoint for CineGen AI."""

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

load_dotenv(Path(__file__).with_name(".env"))

from database import init_db
from routes.auth import router as auth_router
from routes.generate import router as generate_router
from routes.history import router as history_router
from routes.saas import router as saas_router
from routes.video import router as video_router
from utils.logger import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)

OUTPUTS_DIR = Path("outputs")
IMAGES_DIR = OUTPUTS_DIR / "images"
AUDIO_DIR = OUTPUTS_DIR / "audio"
VIDEOS_DIR = OUTPUTS_DIR / "videos"
MUSIC_DIR = Path("assets") / "music"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
MUSIC_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="CineGen AI",
    description=(
        "Accept a story, extract logical scenes, generate cinematic prompts, "
        "optionally generate scene images, store the output as JSON, and "
        "return complete or partial structured results."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(saas_router)
app.include_router(generate_router)
app.include_router(history_router)
app.include_router(video_router)
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")


@app.on_event("startup")
async def startup_event() -> None:
    """Optionally create local/dev database tables."""
    if os.getenv("CINEGEN_AUTO_CREATE_DB", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        init_db()


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return a concise API error for invalid request payloads."""
    logger.warning("Invalid request payload for %s: %s", request.url.path, exc.errors())
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "message": "Invalid request payload.",
            "errors": exc.errors(),
        },
    )


@app.get("/", tags=["Health"])
async def root() -> dict[str, str]:
    """Return a lightweight health response."""
    return {"message": "CineGen AI API is running"}


@app.get("/style.css", include_in_schema=False)
async def stylesheet() -> FileResponse:
    """Serve the vanilla frontend stylesheet for app page routes."""
    return FileResponse("style.css", media_type="text/css")


@app.get("/script.js", include_in_schema=False)
async def frontend_script() -> FileResponse:
    """Serve the vanilla frontend script for app page routes."""
    return FileResponse("script.js", media_type="application/javascript")


@app.get("/index.html", include_in_schema=False)
async def frontend_index() -> FileResponse:
    """Serve the CineGen AI frontend."""
    return FileResponse("index.html", media_type="text/html")


@app.get("/login", include_in_schema=False)
@app.get("/register", include_in_schema=False)
@app.get("/forgot-password", include_in_schema=False)
@app.get("/dashboard", include_in_schema=False)
@app.get("/generate", include_in_schema=False)
@app.get("/history-page", include_in_schema=False)
@app.get("/images", include_in_schema=False)
@app.get("/videos", include_in_schema=False)
@app.get("/profile", include_in_schema=False)
@app.get("/settings", include_in_schema=False)
async def frontend_page() -> FileResponse:
    """Serve the SPA shell for authenticated frontend pages."""
    return FileResponse("index.html", media_type="text/html")
