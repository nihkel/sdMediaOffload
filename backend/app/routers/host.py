"""Endpoints called by the host-agent running on the Proxmox host."""
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import settings
from ..db import get_session
from ..services.queue import import_worker


router = APIRouter()


def require_host_token(x_host_token: str = Header(default="")):
    if x_host_token != settings.host_token:
        raise HTTPException(status_code=401, detail="invalid host token")


@router.post("/device-attached", dependencies=[Depends(require_host_token)])
async def device_attached(payload: schemas.HostDeviceAttached, s: Session = Depends(get_session)):
    device = _upsert_device(s, payload)

    imp = models.Import(
        device_id=device.id,
        mount_path=payload.mount_path,
        status="pending",
    )
    s.add(imp)
    s.add(models.Event(level="info", source="host", device_id=device.id,
                       message=f"Device attached at {payload.mount_path}",
                       data={"label": payload.label, "fs_type": payload.fs_type}))
    s.commit()
    s.refresh(imp)

    await import_worker.enqueue(imp.id)
    return {"device_id": device.id, "import_id": imp.id}


@router.post("/device-detached", dependencies=[Depends(require_host_token)])
def device_detached(payload: schemas.HostDeviceDetached, s: Session = Depends(get_session)):
    q = s.query(models.Device)
    if payload.fs_uuid:
        q = q.filter(models.Device.fs_uuid == payload.fs_uuid)
    elif payload.serial:
        q = q.filter(models.Device.serial == payload.serial)
    else:
        return {"ok": True}

    device = q.first()
    if device:
        s.add(models.Event(level="info", source="host", device_id=device.id,
                           message=f"Device detached from {payload.mount_path}"))
        s.commit()
    return {"ok": True}


def _upsert_device(s: Session, payload: schemas.HostDeviceAttached) -> models.Device:
    q = s.query(models.Device)
    device = None
    if payload.fs_uuid:
        device = q.filter(models.Device.fs_uuid == payload.fs_uuid).one_or_none()
    if not device and payload.serial:
        device = q.filter(models.Device.serial == payload.serial).one_or_none()

    if device is None:
        device = models.Device(
            fs_uuid=payload.fs_uuid, serial=payload.serial, label=payload.label,
            fs_type=payload.fs_type, size_bytes=payload.size_bytes,
        )
        s.add(device)
        s.flush()
    else:
        if payload.label:
            device.label = payload.label
        if payload.fs_type:
            device.fs_type = payload.fs_type
        if payload.size_bytes:
            device.size_bytes = payload.size_bytes
        device.last_seen = datetime.utcnow()

    return device
