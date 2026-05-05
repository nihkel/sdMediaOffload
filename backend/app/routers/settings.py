import shutil

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import settings as app_settings
from ..db import get_session


router = APIRouter()


@router.get("/info")
def info():
    free = total = used = None
    try:
        usage = shutil.disk_usage(app_settings.destination_root)
        total, used, free = usage.total, usage.used, usage.free
    except OSError:
        pass
    return {
        "destination_root": str(app_settings.destination_root),
        "default_template": app_settings.default_template,
        "db_path": str(app_settings.db_path),
        "host_agent_configured": bool(app_settings.host_agent_url),
        "notify_configured": bool(app_settings.notify_url),
        "destination_free_bytes": free,
        "destination_total_bytes": total,
        "destination_used_bytes": used,
    }


@router.get("/camera-profiles", response_model=list[schemas.CameraProfileOut])
def list_profiles(s: Session = Depends(get_session)):
    return s.query(models.CameraProfile).order_by(models.CameraProfile.slug).all()


@router.put("/camera-profiles/{slug}", response_model=schemas.CameraProfileOut)
def upsert_profile(slug: str, payload: schemas.CameraProfileUpsert, s: Session = Depends(get_session)):
    if payload.slug != slug:
        raise HTTPException(400, "slug mismatch")
    p = s.query(models.CameraProfile).filter_by(slug=slug).one_or_none()
    if p is None:
        p = models.CameraProfile(slug=slug, name=payload.name,
                                 detection_rules=payload.detection_rules,
                                 dest_template=payload.dest_template)
        s.add(p)
    else:
        p.name = payload.name
        p.detection_rules = payload.detection_rules
        p.dest_template = payload.dest_template
    s.commit()
    s.refresh(p)
    return p


@router.delete("/camera-profiles/{slug}")
def delete_profile(slug: str, s: Session = Depends(get_session)):
    p = s.query(models.CameraProfile).filter_by(slug=slug).one_or_none()
    if not p:
        raise HTTPException(404)
    if slug == "unknown":
        raise HTTPException(400, "cannot delete the fallback 'unknown' profile")
    s.delete(p)
    s.commit()
    return {"ok": True}
