import shutil

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import settings as app_settings
from ..db import get_session


router = APIRouter()


@router.get("/ha-summary")
def ha_summary(s: Session = Depends(get_session)):
    """Compact, single-call summary tailored for Home Assistant REST sensors.

    Returns the top-level state (overall_status), counters, free space, and the
    currently active import (if any) flattened into top-level keys for easy
    Jinja templating in HA.
    """
    free = total = used = None
    try:
        usage = shutil.disk_usage(app_settings.destination_root)
        total, used, free = usage.total, usage.used, usage.free
    except OSError:
        pass

    total_files = s.query(func.count(models.MediaFile.id)).scalar() or 0
    total_bytes = s.query(func.coalesce(func.sum(models.MediaFile.size_bytes), 0)).scalar() or 0
    devices_count = s.query(func.count(models.Device.id)).scalar() or 0

    active = (s.query(models.Import)
              .filter(models.Import.status.in_(("pending", "scanning", "copying", "paused")))
              .order_by(models.Import.started_at.desc())
              .first())

    overall = "idle"
    progress_pct = 0
    active_payload = None
    if active:
        overall = active.status
        if active.files_total:
            done = active.files_new + active.files_skipped + active.files_failed
            progress_pct = min(100, int(done * 100 / active.files_total))
        active_payload = {
            "id": active.id,
            "status": active.status,
            "camera": (active.camera_profile.name if active.camera_profile else None),
            "device_label": (active.device.label if active.device else None),
            "device_uuid": (active.device.fs_uuid if active.device else None),
            "files_total": active.files_total,
            "files_new": active.files_new,
            "files_skipped": active.files_skipped,
            "files_failed": active.files_failed,
            "bytes_total": active.bytes_total,
            "bytes_copied": active.bytes_copied,
            "started_at": active.started_at.isoformat() if active.started_at else None,
        }

    return {
        "overall_status": overall,            # idle | pending | scanning | copying | paused
        "progress_pct": progress_pct,
        "active_import": active_payload,
        "library_total_files": int(total_files),
        "library_total_bytes": int(total_bytes),
        "library_total_human": _human_bytes(int(total_bytes)),
        "devices_count": int(devices_count),
        "destination_free_bytes": free,
        "destination_total_bytes": total,
        "destination_used_bytes": used,
        "destination_free_human": _human_bytes(free or 0),
        "destination_root": str(app_settings.destination_root),
    }


def _human_bytes(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    v = float(n or 0)
    i = 0
    while v >= 1024 and i < len(units) - 1:
        v /= 1024
        i += 1
    return f"{v:.1f} {units[i]}" if i else f"{int(v)} B"


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
