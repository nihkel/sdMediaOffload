from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import settings as app_settings
from ..db import get_session
from ..services import thumbnails as thumbs


router = APIRouter()


@router.get("", response_model=list[schemas.MediaFileOut])
def list_files(
    camera: str | None = None,
    year: int | None = None,
    month: int | None = None,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    s: Session = Depends(get_session),
):
    q = s.query(models.MediaFile)
    if camera:
        q = q.join(models.Import, models.Import.id == models.MediaFile.first_import_id)\
             .join(models.CameraProfile, models.CameraProfile.id == models.Import.camera_profile_id)\
             .filter(models.CameraProfile.slug == camera)
    if year:
        q = q.filter(func.strftime("%Y", models.MediaFile.captured_at) == f"{year:04d}")
    if month:
        q = q.filter(func.strftime("%m", models.MediaFile.captured_at) == f"{month:02d}")
    return q.order_by(models.MediaFile.captured_at.desc()).offset(offset).limit(limit).all()


@router.get("/stats")
def stats(s: Session = Depends(get_session)):
    total = s.query(func.count(models.MediaFile.id)).scalar() or 0
    bytes_total = s.query(func.coalesce(func.sum(models.MediaFile.size_bytes), 0)).scalar() or 0
    by_camera = (s.query(models.CameraProfile.slug, func.count(models.MediaFile.id))
                 .join(models.Import, models.Import.camera_profile_id == models.CameraProfile.id)
                 .join(models.MediaFile, models.MediaFile.first_import_id == models.Import.id)
                 .group_by(models.CameraProfile.slug)
                 .all())
    return {
        "total_files": total,
        "total_bytes": int(bytes_total),
        "by_camera": [{"slug": s_, "count": c} for s_, c in by_camera],
    }


@router.get("/{file_id}", response_model=schemas.MediaFileOut)
def get_file(file_id: int, s: Session = Depends(get_session)):
    f = s.get(models.MediaFile, file_id)
    if not f:
        raise HTTPException(404)
    return f


@router.get("/{file_id}/thumb", response_class=FileResponse)
def get_thumb(file_id: int, s: Session = Depends(get_session)):
    f = s.get(models.MediaFile, file_id)
    if not f:
        raise HTTPException(404)
    p = thumbs.thumb_path_for(app_settings.thumbs_dir, file_id)
    if not p.is_file():
        # Generate on demand if dest still exists (covers backfill of pre-existing media)
        dest = Path(f.dest_path)
        if dest.is_file():
            thumbs.generate(dest, p)
    if not p.is_file():
        raise HTTPException(404, "no thumbnail")
    return FileResponse(p, media_type="image/jpeg")


@router.get("/{file_id}/raw", response_class=FileResponse)
def get_raw(file_id: int, s: Session = Depends(get_session)):
    f = s.get(models.MediaFile, file_id)
    if not f:
        raise HTTPException(404)
    p = Path(f.dest_path)
    if not p.is_file():
        raise HTTPException(404, "file missing on disk")
    return FileResponse(p, media_type=f.mime_type or "application/octet-stream",
                        filename=f.original_name)
