from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_session
from ..services.queue import import_worker
from ..services.reorganize import reorganize_import
from ..services.ws_broker import broker


router = APIRouter()


TERMINAL_STATUSES = {"done", "failed", "cancelled"}
RUNNING_STATUSES = {"pending", "scanning", "copying"}


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


@router.post("/{import_id}/pause", response_model=schemas.ImportOut)
async def pause_import(import_id: int, s: Session = Depends(get_session)):
    imp = s.get(models.Import, import_id)
    if not imp:
        raise HTTPException(404)
    if imp.status not in RUNNING_STATUSES:
        raise HTTPException(400, f"Cannot pause import in status '{imp.status}'")
    imp.status = "paused"
    s.add(models.Event(level="info", source="api", import_id=imp.id,
                       device_id=imp.device_id, message="Import paused by user"))
    s.commit()
    s.refresh(imp)
    await broker.publish({"import_id": imp.id, "status": imp.status, "event": "paused"})
    return imp


@router.post("/{import_id}/cancel", response_model=schemas.ImportOut)
async def cancel_import(import_id: int, s: Session = Depends(get_session)):
    imp = s.get(models.Import, import_id)
    if not imp:
        raise HTTPException(404)
    if imp.status in TERMINAL_STATUSES:
        raise HTTPException(400, f"Cannot cancel import in terminal status '{imp.status}'")
    imp.status = "cancelled"
    imp.finished_at = datetime.utcnow()
    s.add(models.Event(level="warn", source="api", import_id=imp.id,
                       device_id=imp.device_id, message="Import cancelled by user"))
    s.commit()
    s.refresh(imp)
    await broker.publish({"import_id": imp.id, "status": imp.status, "event": "cancelled"})
    return imp


@router.post("/{import_id}/resume", response_model=schemas.ImportOut)
async def resume_import(import_id: int, s: Session = Depends(get_session)):
    imp = s.get(models.Import, import_id)
    if not imp:
        raise HTTPException(404)
    if imp.status != "paused":
        raise HTTPException(400, f"Can only resume paused imports (current: '{imp.status}')")
    imp.status = "pending"
    s.add(models.Event(level="info", source="api", import_id=imp.id,
                       device_id=imp.device_id, message="Import resumed by user"))
    s.commit()
    s.refresh(imp)
    await import_worker.enqueue(imp.id)
    await broker.publish({"import_id": imp.id, "status": imp.status, "event": "resumed"})
    return imp


@router.post("/{import_id}/reorganize")
async def reorganize_endpoint(import_id: int, s: Session = Depends(get_session)):
    imp = s.get(models.Import, import_id)
    if not imp:
        raise HTTPException(404)
    if imp.status in {"scanning", "copying", "pending"}:
        raise HTTPException(409, f"Import is {imp.status}; pause or cancel before reorganizing")
    result = reorganize_import(s, import_id)
    await broker.publish({"import_id": import_id, "event": "reorganized", **result})
    return result


@router.post("/{import_id}/set-camera/{slug}", response_model=schemas.ImportOut)
async def set_camera(import_id: int, slug: str, s: Session = Depends(get_session)):
    imp = s.get(models.Import, import_id)
    if not imp:
        raise HTTPException(404)
    profile = s.query(models.CameraProfile).filter_by(slug=slug).one_or_none()
    if not profile:
        raise HTTPException(404, f"Camera profile '{slug}' not found")
    imp.camera_profile_id = profile.id
    if imp.device:
        imp.device.detected_camera_id = profile.id
    s.add(models.Event(level="info", source="api", import_id=imp.id,
                       device_id=imp.device_id,
                       message=f"Camera profile manually set to '{slug}'"))
    s.commit()
    s.refresh(imp)
    await broker.publish({"import_id": imp.id, "event": "camera_changed", "slug": slug})
    return imp


@router.post("/{import_id}/retry", response_model=schemas.ImportOut)
async def retry_import(import_id: int, s: Session = Depends(get_session)):
    """Re-queue a failed/cancelled import. Already-imported files are skipped via dedup."""
    imp = s.get(models.Import, import_id)
    if not imp:
        raise HTTPException(404)
    if imp.status not in {"failed", "cancelled"}:
        raise HTTPException(400, f"Can only retry failed/cancelled imports (current: '{imp.status}')")
    imp.status = "pending"
    imp.error = None
    imp.finished_at = None
    s.add(models.Event(level="info", source="api", import_id=imp.id,
                       device_id=imp.device_id, message="Import retried by user"))
    s.commit()
    s.refresh(imp)
    await import_worker.enqueue(imp.id)
    await broker.publish({"import_id": imp.id, "status": imp.status, "event": "retried"})
    return imp
