from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_session


router = APIRouter()


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
