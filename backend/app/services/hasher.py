"""Partial-hash strategy for fast dedup.

For files <= SMALL_FILE_THRESHOLD: full SHA-256.
Otherwise: SHA-256 over (first CHUNK bytes ‖ last CHUNK bytes ‖ size_bytes encoded).
The size is folded into the hash so two different-sized files with identical heads/tails
cannot collide.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

CHUNK = 4 * 1024 * 1024  # 4 MiB
SMALL_FILE_THRESHOLD = 2 * CHUNK  # 8 MiB — below this, full hash is cheap


def partial_hash(path: Path) -> tuple[str, int]:
    size = path.stat().st_size
    h = hashlib.sha256()
    with path.open("rb") as f:
        if size <= SMALL_FILE_THRESHOLD:
            while chunk := f.read(1024 * 1024):
                h.update(chunk)
        else:
            head = f.read(CHUNK)
            h.update(head)
            f.seek(size - CHUNK, os.SEEK_SET)
            tail = f.read(CHUNK)
            h.update(tail)
        h.update(size.to_bytes(8, "little"))
    return h.hexdigest(), size


def full_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()
