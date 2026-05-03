from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_session


router = APIRouter()


@router.get("", response_model=list[schemas.ImportOut])
def list_imports(
    status: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    s: Session = Depends(get_session),
):
    q = s.query(models.Import)
    if status:
        q = q.filter(models.Import.status == status)
    return q.order_by(models.Import.started_at.desc()).offset(offset).limit(limit).all()


@router.get("/active", response_model=list[schemas.ImportOut])
def active_imports(s: Session = Depends(get_session)):
    return (s.query(models.Import)
            .filter(models.Import.status.in_(("pending", "scanning", "copying")))
            .order_by(models.Import.started_at.desc())
            .all())


@router.get("/{import_id}", response_model=schemas.ImportOut)
def get_import(import_id: int, s: Session = Depends(get_session)):
    imp = s.get(models.Import, import_id)
    if not imp:
        raise HTTPException(404)
    return imp


@router.get("/{import_id}/files", response_model=list[schemas.MediaFileOut])
def import_files(import_id: int, s: Session = Depends(get_session)):
    return (s.query(models.MediaFile)
            .filter_by(first_import_id=import_id)
            .order_by(models.MediaFile.captured_at.desc())
            .all())


@router.get("/{import_id}/skips")
def import_skips(import_id: int, s: Session = Depends(get_session)):
    rows = s.query(models.ImportSkip).filter_by(import_id=import_id).all()
    return [
        {"id": r.id, "original_path": r.original_path, "reason": r.reason,
         "matched_media_id": r.matched_media_id, "detail": r.detail}
        for r in rows
    ]


@router.get("/{import_id}/events", response_model=list[schemas.EventOut])
def import_events(import_id: int, s: Session = Depends(get_session)):
    return (s.query(models.Event)
            .filter_by(import_id=import_id)
            .order_by(models.Event.ts.asc())
            .all())
