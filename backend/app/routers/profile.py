"""User profile — the self-reported name / date of birth / country the account dashboard
shows and the profile-setup screen writes. `userId` comes only from the validated JWT
(`get_current_user_id`); the profile is stored and read in the caller's own partition.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.auth.dependency import get_current_user_id
from app.data.profile_store import get_profile, upsert_profile

router = APIRouter(prefix="/profile", tags=["profile"])

_MAX_NAME = 120
_MAX_COUNTRY = 80
_MAX_DOB = 10  # "DD/MM/YYYY"


class ProfileResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    full_name: str = Field(..., alias="fullName")
    date_of_birth: str = Field(..., alias="dateOfBirth")
    country: str
    completed_at: str = Field("", alias="completedAt")


class ProfileRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    full_name: str = Field(..., alias="fullName", min_length=1, max_length=_MAX_NAME)
    date_of_birth: str = Field(..., alias="dateOfBirth", min_length=1, max_length=_MAX_DOB)
    country: str = Field(..., min_length=1, max_length=_MAX_COUNTRY)


@router.get("", response_model=ProfileResponse)
def get(user_id: str = Depends(get_current_user_id)) -> ProfileResponse:
    profile = get_profile(user_id)
    if profile is None:
        # 404 lets the frontend route to the profile-setup screen for a first-time user.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not set")
    return ProfileResponse(
        full_name=profile.full_name,
        date_of_birth=profile.date_of_birth,
        country=profile.country,
        completed_at=profile.completed_at,
    )


@router.put("", response_model=ProfileResponse)
def put(payload: ProfileRequest, user_id: str = Depends(get_current_user_id)) -> ProfileResponse:
    profile = upsert_profile(
        user_id,
        full_name=payload.full_name,
        date_of_birth=payload.date_of_birth,
        country=payload.country,
    )
    return ProfileResponse(
        full_name=profile.full_name,
        date_of_birth=profile.date_of_birth,
        country=profile.country,
        completed_at=profile.completed_at,
    )
