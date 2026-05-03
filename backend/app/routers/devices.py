import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import settings
from ..db import get_session
from ..services.ws_broker import broker


router = APIRouter()
log = logging.getLogger("sdoffload.devices")


@router.get("", response_model=list[schemas.DeviceOut])
def list_devices(s: Session = Depends(get_session)):
    return s.query(models.Device).order_by(models.Device.last_seen.desc()).all()


@router.get("/{device_id}", response_model=schemas.DeviceOut)
def get_device(device_id: int, s: Session = Depends(get_session)):
    d = s.get(models.Device, device_id)
    if not d:
        raise HTTPException(404)
    return d


@router.get("/{device_id}/imports", response_model=list[schemas.ImportOut])
def device_imports(device_id: int, s: Session = Depends(get_session)):
    return (s.query(models.Import)
            .filter_by(device_id=device_id)
            .order_by(models.Import.started_at.desc())
            .all())


@router.post("/{device_id}/eject")
async def eject_device(device_id: int, s: Session = Depends(get_session)):
    if not settings.host_agent_url:
        raise HTTPException(501, "Eject not configured. Set SDOFFLOAD_HOST_AGENT_URL on the backend.")

    device = s.get(models.Device, device_id)
    if not device:
        raise HTTPException(404)

    # Use the most recent import's mount_path as the "current" mount of this device
    last_import = (s.query(models.Import)
                   .filter_by(device_id=device_id)
                   .order_by(models.Import.started_at.desc())
                   .first())
    if not last_import:
        raise HTTPException(400, "No mount path on record for this device")

    # Don't eject while it's actively being read
    if last_import.status in ("scanning", "copying", "pending"):
        raise HTTPException(409, f"Import #{last_import.id} is still {last_import.status}; pause or cancel first")

    url = settings.host_agent_url.rstrip("/") + "/eject"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(url, json={"mount_path": last_import.mount_path},
                                  headers={"X-Host-Token": settings.host_token})
        if r.status_code >= 400:
            raise HTTPException(r.status_code, f"Host-agent eject failed: {r.text[:200]}")
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Could not reach host-agent at {url}: {exc}") from exc

    s.add(models.Event(level="info", source="api", device_id=device.id,
                       message=f"Device ejected via UI ({last_import.mount_path})"))
    s.commit()
    await broker.publish({"event": "device_ejected", "device_id": device_id})
    return {"ok": True, "mount_path": last_import.mount_path}
