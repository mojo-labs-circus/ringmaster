"""api/routes/profile.py
Profile endpoints — read and update the current user's profile.
All endpoints require a valid JWT via get_current_user.
"""

from fastapi import APIRouter, Depends

from api.dependencies import get_current_user
from api.schemas import ProfileResponse, ProfileUpdateRequest
from db.auth.factory import get_auth_repository
from db.auth.models import User
from db.auth.repository import AuthRepository

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=ProfileResponse)
def get_profile(user: User = Depends(get_current_user)) -> ProfileResponse:
    return ProfileResponse(
        username=user.username,
        tier=user.tier,
        assistant_name=user.assistant_name,
    )


@router.patch("", response_model=ProfileResponse)
def update_profile(
    body: ProfileUpdateRequest,
    user: User = Depends(get_current_user),
    repo: AuthRepository = Depends(get_auth_repository),
) -> ProfileResponse:
    repo.update_assistant_name(user.username, body.assistant_name)
    # Re-fetch to guarantee the response reflects what's actually in the DB,
    # then delegate to get_profile to avoid duplicating the response construction
    updated = repo.get_user(user.username)
    return get_profile(user=updated)
