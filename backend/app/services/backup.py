"""Periodic SQLite snapshots into <destination>/.sdoffload-backups/.

Uses the SQLite backup API (online, safe with active connections — copies pages atomically).
"""
from __future__ import annotations

import asyncio
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from ..config import settings


log = logging.getLogger("sdoffload.backup")
BACKUP_DIRNAME = ".sdoffload-backups"


def backup_dir() -> Path:
    return settings.destination_root / BACKUP_DIRNAME


def backup_now() -> Path | None:
    src = settings.db_path
    if not src.is_file():
        log.warning("DB not found at %s, skipping backup", src)
        return None
    bdir = backup_dir()
    try:
        bdir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        log.warning("cannot create backup dir %s: %s", bdir, exc)
        return None

    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    dest = bdir / f"sdoffload-{ts}.db"
    src_conn = sqlite3.connect(str(src))
    dst_conn = sqlite3.connect(str(dest))
    try:
        with dst_conn:
            src_conn.backup(dst_conn)
    finally:
        src_conn.close()
        dst_conn.close()
    log.info("DB backup written to %s (%s bytes)", dest, dest.stat().st_size)

    _prune(bdir, settings.backup_keep_count)
    return dest


def _prune(dir: Path, keep: int) -> None:
    if keep <= 0:
        return
    files = sorted(dir.glob("sdoffload-*.db"), key=lambda p: p.stat().st_mtime)
    for old in files[:-keep]:
        try:
            old.unlink()
            log.info("Pruned old backup %s", old.name)
        except OSError:
            pass


def list_backups() -> list[dict]:
    bdir = backup_dir()
    if not bdir.is_dir():
        return []
    out = []
    for p in sorted(bdir.glob("sdoffload-*.db"), key=lambda p: p.stat().st_mtime, reverse=True):
        st = p.stat()
        out.append({
            "name": p.name,
            "path": str(p),
            "size_bytes": st.st_size,
            "mtime": datetime.utcfromtimestamp(st.st_mtime).isoformat() + "Z",
        })
    return out


async def _periodic_loop():
    interval = max(1, settings.backup_interval_hours) * 3600
    while True:
        try:
            await asyncio.to_thread(backup_now)
        except Exception:
            log.exception("backup failed")
        await asyncio.sleep(interval)


async def start_backup_loop() -> asyncio.Task | None:
    if settings.backup_interval_hours <= 0:
        log.info("DB backups disabled (backup_interval_hours <= 0)")
        return None
    log.info("Scheduling DB backups every %sh, keep %d", settings.backup_interval_hours, settings.backup_keep_count)
    return asyncio.create_task(_periodic_loop(), name="db-backup")
