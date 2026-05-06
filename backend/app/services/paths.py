"""Path/template helpers shared between importer and reorganize."""
from __future__ import annotations

from pathlib import Path


def render_template(template: str, ctx: dict) -> Path:
    formatted = template.format(**ctx)
    parts = [safe_segment(p) for p in formatted.split("/") if p]
    return Path(*parts)


def safe_segment(s: str) -> str:
    bad = '<>:"|?*\x00'
    cleaned = "".join("_" if c in bad else c for c in s).strip(" .")
    return cleaned or "_"


def ensure_unique(dest: Path) -> Path:
    if not dest.exists():
        return dest
    stem, suffix = dest.stem, dest.suffix
    n = 1
    while True:
        candidate = dest.with_name(f"{stem}__{n}{suffix}")
        if not candidate.exists():
            return candidate
        n += 1
