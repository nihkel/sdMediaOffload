"""Reorganize already-imported files into a different camera-profile / template layout.

Atomic per file: each move is shutil.move + DB update in the same transaction.
On failure we leave the file alone, log, and continue.
"""
from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from .paths import ensure_unique, render_template


log = logging.getLogger("sdoffload.reorganize")


def reorganize_import(session: Session, import_id: int) -> dict:
    imp = session.get(models.Import, import_id)
    if imp is None:
        return {"error": "import not found"}

    profile = imp.camera_profile if imp.camera_profile_id else None
    template = (profile.dest_template if profile else settings.default_template)
    camera_slug = (profile.slug if profile else "unknown")

    files = (session.query(models.MediaFile)
             .filter_by(first_import_id=import_id)
             .order_by(models.MediaFile.id)
             .all())

    moved = 0
    skipped = 0
    failed = 0
    touched_dirs: set[Path] = set()

    for f in files:
        captured = f.captured_at or imp.started_at or datetime.utcnow()
        old_path = Path(f.dest_path)
        ctx = {
            "camera_slug": camera_slug,
            "captured": captured,
            "original_name": f.original_name,
            "original_stem": Path(f.original_name).stem,
            "original_ext": Path(f.original_name).suffix.lstrip("."),
            "device_label": (imp.device.label if imp.device else ""),
            "device_uuid": (imp.device.fs_uuid if imp.device else ""),
        }
        try:
            new_rel = render_template(template, ctx)
        except KeyError as exc:
            log.warning("template var missing for %s: %s", f.id, exc)
            failed += 1
            continue
        new_path = settings.destination_root / new_rel
        if new_path == old_path and old_path.exists():
            skipped += 1
            continue
        if not old_path.exists():
            log.warning("source missing for media #%s at %s", f.id, old_path)
            failed += 1
            continue
        try:
            new_path.parent.mkdir(parents=True, exist_ok=True)
            new_path = ensure_unique(new_path)
            shutil.move(str(old_path), str(new_path))
            f.dest_path = str(new_path)
            session.add(models.Event(
                level="info", source="reorganize", import_id=import_id,
                device_id=imp.device_id,
                message=f"Moved media #{f.id}",
                data={"from": str(old_path), "to": str(new_path)},
            ))
            session.commit()
            touched_dirs.add(old_path.parent)
            moved += 1
        except OSError as exc:
            log.exception("move failed: %s -> %s", old_path, new_path)
            session.rollback()
            failed += 1
            session.add(models.Event(
                level="error", source="reorganize", import_id=import_id,
                device_id=imp.device_id,
                message=f"Move failed for media #{f.id}: {exc}",
            ))
            session.commit()

    # Best-effort cleanup of now-empty directories under destination_root
    for d in sorted(touched_dirs, key=lambda p: -len(p.parts)):
        try:
            d.rmdir()
            # Walk up while still under destination_root and empty
            parent = d.parent
            while parent != settings.destination_root and parent.is_dir() and not any(parent.iterdir()):
                parent.rmdir()
                parent = parent.parent
        except OSError:
            pass

    return {"moved": moved, "skipped": skipped, "failed": failed, "total": len(files)}
