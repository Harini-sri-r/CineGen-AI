"""Protected SaaS API routes for CineGen AI."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from auth_dependencies import get_current_user
from database import get_db
from db_models import User, UserSettings, utc_now
from models.saas import (
    DashboardResponse,
    ImageLibraryResponse,
    MessageResponse,
    PaginatedHistoryResponse,
    PasswordChangeRequest,
    ProfileResponse,
    ProfileUpdateRequest,
    StoryDetailResponse,
    UserSettingsResponse,
    UserSettingsUpdateRequest,
    VideoLibraryResponse,
)
from services.auth_service import hash_password, verify_password
from services.saas_service import (
    build_dashboard,
    delete_image_for_user,
    delete_story_for_user,
    delete_video_for_user,
    get_story_for_user,
    list_history_cards,
    list_image_library,
    list_video_library,
    profile_response,
    settings_response,
    story_detail_response,
)

router = APIRouter(prefix="/api", tags=["SaaS"])


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    status_code=status.HTTP_200_OK,
    summary="Return the authenticated user's dashboard",
)
async def dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardResponse:
    """Return dashboard counters, recent stories, and activity."""
    return build_dashboard(db, current_user)


@router.get(
    "/statistics",
    response_model=DashboardResponse,
    status_code=status.HTTP_200_OK,
    summary="Return dashboard statistics",
)
async def statistics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardResponse:
    """Return the same payload as the dashboard for chart-friendly clients."""
    return build_dashboard(db, current_user)


@router.get(
    "/history",
    response_model=PaginatedHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Return paginated user history",
)
async def history(
    search: str = "",
    sort: str = Query(default="newest", pattern="^(newest|oldest)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaginatedHistoryResponse:
    """Return only the authenticated user's generation history."""
    return list_history_cards(
        db,
        current_user,
        search=search,
        sort=sort,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/stories",
    response_model=PaginatedHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Return paginated user stories",
)
async def stories(
    search: str = "",
    sort: str = Query(default="newest", pattern="^(newest|oldest)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaginatedHistoryResponse:
    """Alias for history, kept for REST resource naming."""
    return list_history_cards(
        db,
        current_user,
        search=search,
        sort=sort,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/stories/{story_id}",
    response_model=StoryDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Return a user-owned story",
)
async def story_detail(
    story_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StoryDetailResponse:
    """Return a full story detail for the owner."""
    story = get_story_for_user(db, current_user, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="Story not found.")

    return story_detail_response(story)


@router.delete(
    "/stories/{story_id}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete a story from user history",
)
async def delete_story(
    story_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Delete story metadata for the authenticated user."""
    if not delete_story_for_user(db, current_user, story_id):
        raise HTTPException(status_code=404, detail="Story not found.")

    return MessageResponse(message="Story deleted.")


@router.delete(
    "/history/{story_id}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete a story from user history",
)
async def delete_history_story(
    story_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Delete via the history resource alias."""
    return await delete_story(story_id, current_user, db)


@router.get(
    "/images",
    response_model=ImageLibraryResponse,
    status_code=status.HTTP_200_OK,
    summary="Return the user's image library",
)
async def images(
    provider: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ImageLibraryResponse:
    """Return all generated images owned by the user."""
    items = list_image_library(db, current_user, provider=provider)
    return ImageLibraryResponse(items=items, total=len(items))


@router.delete(
    "/images/{image_id}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete an image from the user's library",
)
async def delete_image(
    image_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Delete image metadata for the authenticated user."""
    if not delete_image_for_user(db, current_user, image_id):
        raise HTTPException(status_code=404, detail="Image not found.")

    return MessageResponse(message="Image deleted.")


@router.get(
    "/videos",
    response_model=VideoLibraryResponse,
    status_code=status.HTTP_200_OK,
    summary="Return the user's video library",
)
async def videos(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VideoLibraryResponse:
    """Return all generated videos owned by the user."""
    items = list_video_library(db, current_user)
    return VideoLibraryResponse(items=items, total=len(items))


@router.delete(
    "/videos/{video_id}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete a video from the user's library",
)
async def delete_video(
    video_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Delete video metadata for the authenticated user."""
    if not delete_video_for_user(db, current_user, video_id):
        raise HTTPException(status_code=404, detail="Video not found.")

    return MessageResponse(message="Video deleted.")


@router.get(
    "/profile",
    response_model=ProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Return the user's profile",
)
async def profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    """Return profile, settings, and counters."""
    return profile_response(db, current_user)


@router.put(
    "/profile",
    response_model=ProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Update the user's profile",
)
async def update_profile(
    request: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    """Update username, email, or profile picture."""
    if request.email and request.email.lower() != current_user.email:
        existing = db.scalar(
            select(User).where(User.email == request.email.lower(), User.id != current_user.id)
        )
        if existing:
            raise HTTPException(status_code=409, detail="Email already in use.")
        current_user.email = request.email.lower()

    if request.username and request.username != current_user.username:
        existing = db.scalar(
            select(User).where(
                User.username == request.username,
                User.id != current_user.id,
            )
        )
        if existing:
            raise HTTPException(status_code=409, detail="Username already in use.")
        current_user.username = request.username

    if request.profile_picture is not None:
        current_user.profile_picture = request.profile_picture

    db.commit()
    db.refresh(current_user)
    return profile_response(db, current_user)


@router.post(
    "/profile/change-password",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Change the user's password",
)
async def change_password(
    request: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Change password after verifying the current password."""
    if not verify_password(request.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")

    current_user.password_hash = hash_password(request.new_password)
    db.commit()
    return MessageResponse(message="Password changed.")


@router.get(
    "/settings",
    response_model=UserSettingsResponse,
    status_code=status.HTTP_200_OK,
    summary="Return user settings",
)
async def settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserSettingsResponse:
    """Return product preferences."""
    if current_user.settings is None:
        current_user.settings = UserSettings(user_id=current_user.id)
        db.commit()
        db.refresh(current_user)

    return settings_response(current_user.settings)


@router.put(
    "/settings",
    response_model=UserSettingsResponse,
    status_code=status.HTTP_200_OK,
    summary="Update user settings",
)
async def update_settings(
    request: UserSettingsUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserSettingsResponse:
    """Update product preferences."""
    if current_user.settings is None:
        current_user.settings = UserSettings(user_id=current_user.id)
        db.flush()

    settings_record = current_user.settings
    if request.theme is not None:
        settings_record.theme = request.theme
    if request.language is not None:
        settings_record.language = request.language
    if request.voice_selection is not None:
        settings_record.voice_selection = request.voice_selection
    if request.image_provider is not None:
        settings_record.image_provider = request.image_provider
    if request.background_music_enabled is not None:
        settings_record.background_music_enabled = request.background_music_enabled
    settings_record.updated_at = utc_now()
    db.commit()
    db.refresh(settings_record)
    return settings_response(settings_record)
