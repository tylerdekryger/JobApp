import hashlib

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.domain.models import UserProfile
from app.domain.schemas import ProfileResponse, ProfileUpdateRequest

router = APIRouter(prefix="/profile", tags=["profile"])


def _hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest() if text.strip() else ""


def get_or_create_profile(db: Session) -> UserProfile:
    profile = db.get(UserProfile, 1)
    if profile is None:
        profile = UserProfile(id=1, resume_text="", resume_hash="")
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


@router.get("", response_model=ProfileResponse)
def get_profile(db: Session = Depends(get_db)) -> ProfileResponse:
    profile = get_or_create_profile(db)
    return ProfileResponse(
        resume_text=profile.resume_text,
        resume_hash=profile.resume_hash,
        updated_at=profile.updated_at,
    )


@router.put("", response_model=ProfileResponse)
def update_profile(payload: ProfileUpdateRequest, db: Session = Depends(get_db)) -> ProfileResponse:
    profile = get_or_create_profile(db)
    profile.resume_text = payload.resume_text
    profile.resume_hash = _hash(payload.resume_text)
    db.commit()
    db.refresh(profile)
    return ProfileResponse(
        resume_text=profile.resume_text,
        resume_hash=profile.resume_hash,
        updated_at=profile.updated_at,
    )
