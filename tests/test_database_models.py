"""Tests for the SQLAlchemy SaaS data model."""

from sqlalchemy import select

from db_models import Audio, Image, Prompt, Scene, Story, User, Video
from services.auth_service import hash_password
from tests.conftest_saas import clear_test_database_override, use_test_database


def test_database_models_create_full_generation_graph(tmp_path) -> None:
    SessionLocal = use_test_database(tmp_path)

    with SessionLocal() as db:
        user = User(
            username="creator",
            email="creator@example.com",
            password_hash=hash_password("strong-password-123"),
        )
        db.add(user)
        db.flush()
        story = Story(user_id=user.id, story="A moonlit castle.", title="A moonlit castle")
        db.add(story)
        db.flush()
        scene = Scene(story_id=story.story_id, scene_number=1, description="Castle")
        db.add(scene)
        db.flush()
        db.add(Prompt(scene_id=scene.scene_id, prompt_text="cinematic castle"))
        db.add(Image(scene_id=scene.scene_id, image_path="outputs/images/scene_1.png"))
        db.add(Audio(scene_id=scene.scene_id, audio_path="outputs/audio/scene_1.mp3"))
        db.add(Video(story_id=story.story_id, video_path="outputs/videos/story.mp4"))
        db.commit()

    with SessionLocal() as db:
        saved_story = db.scalar(select(Story).where(Story.title == "A moonlit castle"))
        assert saved_story is not None
        assert saved_story.user.email == "creator@example.com"
        assert saved_story.scenes[0].prompt.prompt_text == "cinematic castle"
        assert saved_story.scenes[0].images[0].image_path.endswith("scene_1.png")
        assert saved_story.videos[0].video_path.endswith("story.mp4")

    clear_test_database_override()
