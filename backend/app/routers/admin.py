"""Admin operations: DB backup trigger / list, etc."""
from fastapi import APIRouter, HTTPException

from ..services import backup as backup_svc


router = APIRouter()


@router.get("/backups")
def list_backups():
    return backup_svc.list_backups()


@router.post("/backups/run")
def run_backup_now():
    p = backup_svc.backup_now()
    if not p:
        raise HTTPException(500, "backup failed (see server logs)")
    return {"ok": True, "path": str(p), "size_bytes": p.stat().st_size}
