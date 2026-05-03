"""Importer worker: scan → dedup → copy → record.

Reads files from the (read-only) mount path the host-agent gave us, and writes to
`settings.destination_root`. Originals are NEVER modified or deleted — we only read.
"""
from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from .camera_detect import detect_camera, is_media_file
from .exif import read_exif, mime_for
from .hasher import partial_hash


log = logging.getLogger("sdoffload.importer")


def remap_source(mount_path: str) -> Path:
    """If the VM sees the host's mount under a different prefix (e.g. NFS), remap it."""
    p = Path(mount_path)
    if settings.source_path_remap:
        prefix, _, replacement = settings.source_path_remap.partition(":")
        if prefix and p.is_absolute() and str(p).startswith(prefix):
            return Path(replacement) / p.relative_to(prefix)
    return p


def run_import(session: Session, import_id: int, on_progress=None) -> None:
    imp = session.get(models.Import, import_id)
    if imp is None:
        log.warning("Import %s not found", import_id)
        return

    src_root = remap_source(imp.mount_path)
    if not src_root.exists():
        _fail(session, imp, f"Source path not accessible: {src_root}")
        return

    _emit(session, "info", "importer", imp, f"Starting scan of {src_root}")
    imp.status = "scanning"
    session.commit()

    profiles = [_profile_dict(p) for p in session.query(models.CameraProfile).all()]
    detection = detect_camera(src_root, profiles, probe_exif=lambda p: read_exif(p))
    profile = session.query(models.CameraProfile).filter_by(slug=detection.slug).one_or_none()
    if profile:
        imp.camera_profile_id = profile.id
        if imp.device:
            imp.device.detected_camera_id = profile.id
    _emit(session, "info", "importer", imp,
          f"Camera detected: {detection.slug} (score={detection.score})",
          {"matched": detection.matched})
    session.commit()

    files: list[Path] = sorted(p for p in src_root.rglob("*") if p.is_file() and is_media_file(p))
    imp.files_total = len(files)
    imp.bytes_total = sum(p.stat().st_size for p in files if _safe_exists(p))
    imp.status = "copying"
    session.commit()
    _maybe_progress(on_progress, imp)

    template = (profile.dest_template if profile else settings.default_template)

    for src in files:
        try:
            _import_one(session, imp, src, src_root, profile, template)
        except Exception as exc:
            log.exception("Import error for %s", src)
            imp.files_failed += 1
            session.add(models.ImportSkip(
                import_id=imp.id, original_path=str(src),
                reason="error", detail=str(exc)[:500],
            ))
            session.commit()
        _maybe_progress(on_progress, imp)

    imp.status = "done"
    imp.finished_at = datetime.utcnow()
    session.commit()
    _emit(session, "info", "importer", imp,
          f"Import done: new={imp.files_new} skipped={imp.files_skipped} failed={imp.files_failed}")
    _maybe_progress(on_progress, imp)


def _import_one(session: Session, imp: models.Import, src: Path, src_root: Path,
                profile: Optional[models.CameraProfile], template: str) -> None:
    phash, size = partial_hash(src)

    existing = (session.query(models.MediaFile)
                .filter_by(partial_hash=phash, size_bytes=size, original_name=src.name)
                .one_or_none())
    if existing:
        imp.files_skipped += 1
        session.add(models.ImportSkip(
            import_id=imp.id, original_path=str(src),
            reason="duplicate", matched_media_id=existing.id,
        ))
        session.commit()
        return

    meta = read_exif(src)
    captured = meta.get("captured_at") or datetime.fromtimestamp(src.stat().st_mtime)

    rel = _render_template(template, {
        "camera_slug": (profile.slug if profile else "unknown"),
        "captured": captured,
        "original_name": src.name,
        "original_stem": src.stem,
        "original_ext": src.suffix.lstrip("."),
        "device_label": (imp.device.label if imp.device else ""),
        "device_uuid": (imp.device.fs_uuid if imp.device else ""),
    })
    dest = settings.destination_root / rel
    dest = _ensure_unique(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    shutil.copy2(src, dest)

    media = models.MediaFile(
        partial_hash=phash, size_bytes=size, original_name=src.name,
        mime_type=mime_for(src),
        exif_make=meta.get("make"), exif_model=meta.get("model"),
        captured_at=captured,
        width=meta.get("width"), height=meta.get("height"),
        dest_path=str(dest),
        original_path_on_device=str(src.relative_to(src_root)),
        first_import_id=imp.id, first_device_id=imp.device_id,
        imported_at=datetime.utcnow(),
    )
    session.add(media)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        # A concurrent import got there first; treat as duplicate.
        dest.unlink(missing_ok=True)
        existing = (session.query(models.MediaFile)
                    .filter_by(partial_hash=phash, size_bytes=size, original_name=src.name)
                    .one_or_none())
        imp.files_skipped += 1
        if existing:
            session.add(models.ImportSkip(
                import_id=imp.id, original_path=str(src),
                reason="duplicate-race", matched_media_id=existing.id,
            ))
        session.commit()
        return

    imp.files_new += 1
    imp.bytes_copied += size
    session.commit()


def _render_template(template: str, ctx: dict) -> Path:
    formatted = template.format(**ctx)
    parts = [_safe_segment(p) for p in formatted.split("/") if p]
    return Path(*parts)


def _safe_segment(s: str) -> str:
    bad = '<>:"|?*\x00'
    return "".join("_" if c in bad else c for c in s).strip(" .") or "_"


def _ensure_unique(dest: Path) -> Path:
    if not dest.exists():
        return dest
    stem, suffix = dest.stem, dest.suffix
    n = 1
    while True:
        candidate = dest.with_name(f"{stem}__{n}{suffix}")
        if not candidate.exists():
            return candidate
        n += 1


def _fail(session: Session, imp: models.Import, msg: str) -> None:
    imp.status = "failed"
    imp.error = msg
    imp.finished_at = datetime.utcnow()
    session.add(models.Event(level="error", source="importer", import_id=imp.id,
                             device_id=imp.device_id, message=msg))
    session.commit()


def _emit(session: Session, level: str, source: str, imp: models.Import, message: str, data: dict | None = None):
    session.add(models.Event(level=level, source=source, import_id=imp.id,
                             device_id=imp.device_id, message=message, data=data))
    session.commit()


def _safe_exists(p: Path) -> bool:
    try:
        return p.exists()
    except OSError:
        return False


def _profile_dict(p: models.CameraProfile) -> dict:
    return {"slug": p.slug, "name": p.name, "detection_rules": p.detection_rules,
            "dest_template": p.dest_template}


def _maybe_progress(cb, imp: models.Import) -> None:
    if cb is None:
        return
    try:
        cb({
            "import_id": imp.id, "status": imp.status,
            "files_total": imp.files_total, "files_new": imp.files_new,
            "files_skipped": imp.files_skipped, "files_failed": imp.files_failed,
            "bytes_total": imp.bytes_total, "bytes_copied": imp.bytes_copied,
        })
    except Exception:
        log.exception("progress callback failed")
