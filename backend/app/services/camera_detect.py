"""Camera detection by directory layout, filename patterns and EXIF Make/Model.

Each profile declares `detection_rules`:
  - `dirs`:    list of glob-relative directories under the mount root that, if present, score points
  - `files`:   list of filename glob patterns that, if matched, score points
  - `exif_make`/`exif_model`: substring (case-insensitive) checked against EXIF of any photo

The profile with the highest non-zero score wins. Falls back to the `unknown` profile.
"""
from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


DEFAULT_PROFILES: list[dict] = [
    {
        "slug": "gopro",
        "name": "GoPro Hero",
        "detection_rules": {
            "dirs": ["DCIM/*GOPRO", "MISC"],
            "files": ["GX*.MP4", "GH*.MP4", "GOPR*.JPG", "GP*.JPG"],
            "exif_make": "gopro",
        },
        "dest_template": "{camera_slug}/{captured:%Y}/{captured:%Y-%m-%d}/{original_name}",
    },
    {
        "slug": "sony_a6000",
        "name": "Sony Alpha (A6000 family)",
        "detection_rules": {
            "dirs": ["DCIM/*MSDCF", "PRIVATE/SONY", "AVCHD"],
            "files": ["DSC*.JPG", "DSC*.ARW", "*.MTS", "C*.MP4"],
            "exif_make": "sony",
        },
        "dest_template": "{camera_slug}/{captured:%Y}/{captured:%Y-%m-%d}/{original_name}",
    },
    {
        "slug": "dji_mavic_mini",
        "name": "DJI Mavic Mini",
        "detection_rules": {
            "dirs": ["DCIM/*MEDIA", "MISC/DJI"],
            "files": ["DJI_*.MP4", "DJI_*.JPG", "DJI_*.DNG", "DJI_*.SRT"],
            "exif_make": "dji",
        },
        "dest_template": "{camera_slug}/{captured:%Y}/{captured:%Y-%m-%d}/{original_name}",
    },
    {
        "slug": "unknown",
        "name": "Generic / Unknown",
        "detection_rules": {"dirs": ["DCIM"], "files": ["*.JPG", "*.MP4"]},
        "dest_template": "unknown/{captured:%Y}/{captured:%Y-%m-%d}/{original_name}",
    },
]


@dataclass
class DetectionResult:
    slug: str
    score: int
    matched: list[str]


def detect_camera(mount_root: Path, profiles: Iterable[dict], probe_exif=None) -> DetectionResult:
    """Score each profile against the mount and return the winner.

    `probe_exif` is an optional callable `(path) -> dict|None` returning EXIF data for
    one sample photo; injected so the caller controls which library is used.
    """
    best = DetectionResult(slug="unknown", score=0, matched=[])

    sample_photo: Optional[Path] = None
    for p in mount_root.rglob("*"):
        if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".heic", ".dng", ".arw"}:
            sample_photo = p
            break

    exif_data: dict = {}
    if sample_photo and probe_exif:
        exif_data = probe_exif(sample_photo) or {}

    exif_make = (exif_data.get("make") or "").lower()
    exif_model = (exif_data.get("model") or "").lower()

    for profile in profiles:
        rules = profile.get("detection_rules") or {}
        score = 0
        matched: list[str] = []

        for d in rules.get("dirs", []) or []:
            if any(_glob_dir_match(p, d) for p in mount_root.rglob("*") if p.is_dir()):
                score += 3
                matched.append(f"dir:{d}")

        file_patterns = rules.get("files", []) or []
        if file_patterns:
            for p in mount_root.rglob("*"):
                if not p.is_file():
                    continue
                name = p.name.upper()
                for pat in file_patterns:
                    if fnmatch.fnmatch(name, pat.upper()):
                        score += 1
                        matched.append(f"file:{pat}")
                        break
                if score >= 10:
                    break

        if rules.get("exif_make") and rules["exif_make"].lower() in exif_make:
            score += 5
            matched.append(f"exif_make:{rules['exif_make']}")
        if rules.get("exif_model") and rules["exif_model"].lower() in exif_model:
            score += 5
            matched.append(f"exif_model:{rules['exif_model']}")

        if score > best.score:
            best = DetectionResult(slug=profile["slug"], score=score, matched=matched)

    return best


def _glob_dir_match(path: Path, pattern: str) -> bool:
    parts = pattern.replace("\\", "/").split("/")
    rel = list(path.parts[-len(parts):])
    if len(rel) != len(parts):
        return False
    return all(fnmatch.fnmatchcase(rel[i].upper(), parts[i].upper()) for i in range(len(parts)))


MEDIA_EXTENSIONS = {
    ".jpg", ".jpeg", ".heic", ".heif", ".png", ".dng", ".arw", ".cr2", ".cr3", ".nef", ".raf", ".rw2",
    ".mp4", ".mov", ".m4v", ".mts", ".m2ts", ".avi", ".mkv", ".lrv", ".thm", ".srt", ".wav", ".mp3",
}


def is_media_file(path: Path) -> bool:
    return path.suffix.lower() in MEDIA_EXTENSIONS
