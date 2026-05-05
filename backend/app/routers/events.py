from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_session


router = APIRouter()


@router.get("", response_model=list[schemas.EventOut])
def list_events(
    level: str | None = None,
    source: str | None = None,
    device_id: int | None = None,
    import_id: int | None = None,
    limit: int = Query(200, le=1000),
    offset: int = Query(0, ge=0),
    s: Session = Depends(get_session),
):
    q = s.query(models.Event)
    if level:
        q = q.filter(models.Event.level == level)
    if source:
        q = q.filter(models.Event.source == source)
    if device_id:
        q = q.filter(models.Event.device_id == device_id)
    if import_id:
        q = q.filter(models.Event.import_id == import_id)
    return q.order_by(models.Event.ts.desc()).offset(offset).limit(limit).all()


@router.get("/sources")
def event_sources(s: Session = Depends(get_session)):
    """Distinct values of `source` for the filter dropdown in the UI."""
    rows = s.query(models.Event.source).distinct().all()
    return [r[0] for r in rows if r[0]]
