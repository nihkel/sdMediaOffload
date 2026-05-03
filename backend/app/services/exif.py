"""EXIF / metadata extraction.

Uses `exifread` for stills (pure Python, no native deps needed for development).
For videos, falls back to filesystem mtime — full video metadata extraction can be added
later via ffprobe if needed.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

import exifread


PHOTO_EXTS = {".jpg", ".jpeg", ".heic", ".heif", ".dng", ".arw", ".cr2", ".cr3", ".nef", ".raf", ".rw2", ".tif", ".tiff"}
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".mts", ".m2ts", ".avi", ".mkv", ".lrv"}


def read_exif(path: Path) -> dict:
    out: dict = {"make": None, "model": None, "captured_at": None, "width": None, "height": None}

    if path.suffix.lower() in PHOTO_EXTS:
        try:
            with path.open("rb") as f:
                tags = exifread.process_file(f, details=False, stop_tag="EXIF DateTimeOriginal")
            out["make"] = _str_tag(tags.get("Image Make"))
            out["model"] = _str_tag(tags.get("Image Model"))
            dt = tags.get("EXIF DateTimeOriginal") or tags.get("Image DateTime")
            if dt:
                out["captured_at"] = _parse_exif_dt(str(dt))
            w = tags.get("EXIF ExifImageWidth") or tags.get("Image ImageWidth")
            h = tags.get("EXIF ExifImageLength") or tags.get("Image ImageLength")
            if w:
                out["width"] = int(str(w))
            if h:
                out["height"] = int(str(h))
        except Exception:
            pass

    if not out["captured_at"]:
        try:
            out["captured_at"] = datetime.fromtimestamp(path.stat().st_mtime)
        except Exception:
            pass

    return out


def mime_for(path: Path) -> Optional[str]:
    ext = path.suffix.lower()
    return _MIME.get(ext)


def _str_tag(tag) -> Optional[str]:
    if tag is None:
        return None
    return str(tag).strip() or None


def _parse_exif_dt(s: str) -> Optional[datetime]:
    s = s.strip()
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y:%m:%d %H:%M:%S%z"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


_MIME = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".heic": "image/heic", ".heif": "image/heif",
    ".png": "image/png",
    ".dng": "image/x-adobe-dng", ".arw": "image/x-sony-arw",
    ".cr2": "image/x-canon-cr2", ".cr3": "image/x-canon-cr3",
    ".nef": "image/x-nikon-nef", ".raf": "image/x-fuji-raf", ".rw2": "image/x-panasonic-rw2",
    ".mp4": "video/mp4", ".m4v": "video/mp4", ".mov": "video/quicktime",
    ".mts": "video/mp2t", ".m2ts": "video/mp2t",
    ".avi": "video/x-msvideo", ".mkv": "video/x-matroska",
    ".lrv": "video/mp4",
    ".srt": "application/x-subrip",
    ".thm": "image/jpeg",
}
