from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.digest.service import DigestError, send_daily_digest
from app.domain.models import DigestPreset
from app.domain.schemas import (
    DigestPresetCreate,
    DigestPresetResponse,
    DigestPresetUpdate,
    DigestSendResponse,
)

router = APIRouter(prefix="/digests", tags=["digests"])


@router.get("", response_model=list[DigestPresetResponse])
def list_presets(db: Session = Depends(get_db)) -> list[DigestPreset]:
    return list(db.scalars(select(DigestPreset).order_by(DigestPreset.id)))


@router.post("", response_model=DigestPresetResponse, status_code=201)
def create_preset(payload: DigestPresetCreate, db: Session = Depends(get_db)) -> DigestPreset:
    if not payload.name.strip() or not payload.title_contains.strip():
        raise HTTPException(status_code=422, detail="name and title_contains are required")
    preset = DigestPreset(
        name=payload.name.strip(),
        title_contains=payload.title_contains.strip(),
        is_active=payload.is_active,
    )
    db.add(preset)
    db.commit()
    db.refresh(preset)
    return preset


@router.patch("/{preset_id}", response_model=DigestPresetResponse)
def update_preset(preset_id: int, payload: DigestPresetUpdate, db: Session = Depends(get_db)) -> DigestPreset:
    preset = db.get(DigestPreset, preset_id)
    if preset is None:
        raise HTTPException(status_code=404, detail="Preset not found")
    if payload.name is not None:
        if not payload.name.strip():
            raise HTTPException(status_code=422, detail="name cannot be empty")
        preset.name = payload.name.strip()
    if payload.title_contains is not None:
        if not payload.title_contains.strip():
            raise HTTPException(status_code=422, detail="title_contains cannot be empty")
        preset.title_contains = payload.title_contains.strip()
    if payload.is_active is not None:
        preset.is_active = payload.is_active
    db.commit()
    db.refresh(preset)
    return preset


@router.delete("/{preset_id}", status_code=204)
def delete_preset(preset_id: int, db: Session = Depends(get_db)) -> None:
    preset = db.get(DigestPreset, preset_id)
    if preset is None:
        raise HTTPException(status_code=404, detail="Preset not found")
    db.delete(preset)
    db.commit()


@router.post("/run-now", response_model=DigestSendResponse)
def run_now() -> DigestSendResponse:
    """Send the digest immediately (bypasses schedule). Useful for testing SMTP setup."""
    try:
        result = send_daily_digest()
    except DigestError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return DigestSendResponse(
        presets_run=result.presets_run,
        total_matches=result.total_matches,
        to=result.to,
        subject=result.subject,
        skipped=result.skipped,
    )
