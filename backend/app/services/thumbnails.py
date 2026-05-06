"""Thumbnail generation: PIL for stills, ffmpeg for video."""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from PIL import Image, ImageOps

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except Exception:  # pragma: no cover
    pass


log = logging.getLogger("sdoffload.thumbnails")

THUMB_SIZE = (320, 320)
JPEG_QUALITY = 80

PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".heic", ".heif"}
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".mkv", ".mts", ".m2ts", ".avi", ".lrv", ".webm"}
RAW_EXTS = {".arw", ".cr2", ".cr3", ".nef", ".raf", ".rw2", ".dng", ".srw", ".pef", ".orf"}


def thumb_path_for(thumbs_root: Path, media_id: int) -> Path:
    return thumbs_root / f"{media_id}.jpg"


def generate(src: Path, dest: Path) -> bool:
    """Best-effort thumbnail generation. Returns True if dest now exists."""
    if dest.exists():
        return True
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        log.warning("cannot create thumbs dir %s: %s", dest.parent, exc)
        return False

    ext = src.suffix.lower()
    try:
        if ext in PHOTO_EXTS:
            return _photo(src, dest)
        if ext in RAW_EXTS:
            return _raw(src, dest)
        if ext in VIDEO_EXTS:
            return _video(src, dest)
    except Exception as exc:
        log.warning("thumbnail failed for %s: %s", src, exc)
    return False


def _photo(src: Path, dest: Path) -> bool:
    with Image.open(src) as img:
        img = ImageOps.exif_transpose(img) or img
        img.thumbnail(THUMB_SIZE, Image.Resampling.LANCZOS)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        img.save(dest, "JPEG", quality=JPEG_QUALITY, optimize=True)
    return True


def _raw(src: Path, dest: Path) -> bool:
    """RAW: prefer the embedded JPEG preview; fall back to a half-size decode."""
    import io
    try:
        import rawpy
    except ImportError:
        log.warning("rawpy not installed, cannot thumbnail %s", src)
        return False

    with rawpy.imread(str(src)) as raw:
        try:
            thumb = raw.extract_thumb()
        except rawpy.LibRawNoThumbnailError:
            thumb = None

        if thumb is not None and thumb.format == rawpy.ThumbFormat.JPEG:
            with Image.open(io.BytesIO(thumb.data)) as img:
                img = ImageOps.exif_transpose(img) or img
                img.thumbnail(THUMB_SIZE, Image.Resampling.LANCZOS)
                if img.mode != "RGB":
                    img = img.convert("RGB")
                img.save(dest, "JPEG", quality=JPEG_QUALITY, optimize=True)
            return True

        if thumb is not None and thumb.format == rawpy.ThumbFormat.BITMAP:
            img = Image.fromarray(thumb.data)
            img.thumbnail(THUMB_SIZE, Image.Resampling.LANCZOS)
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(dest, "JPEG", quality=JPEG_QUALITY, optimize=True)
            return True

        # Fallback: half-size demosaic. Slower but always works.
        rgb = raw.postprocess(use_camera_wb=True, half_size=True, output_bps=8, no_auto_bright=False)
        img = Image.fromarray(rgb)
        img.thumbnail(THUMB_SIZE, Image.Resampling.LANCZOS)
        img.save(dest, "JPEG", quality=JPEG_QUALITY, optimize=True)
        return True


def _video(src: Path, dest: Path) -> bool:
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        # seek before -i for fast keyframe seek; if file is shorter, fallback after error
        "-ss", "1", "-i", str(src),
        "-vframes", "1",
        "-vf", f"scale={THUMB_SIZE[0]}:-2:flags=lanczos",
        "-f", "image2", str(dest),
    ]
    try:
        subprocess.run(cmd, check=True, timeout=20, stderr=subprocess.PIPE)
        return dest.exists()
    except subprocess.CalledProcessError:
        # Try without seek for very short clips
        cmd2 = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(src), "-vframes", "1",
            "-vf", f"scale={THUMB_SIZE[0]}:-2:flags=lanczos",
            "-f", "image2", str(dest),
        ]
        subprocess.run(cmd2, check=True, timeout=20, stderr=subprocess.PIPE)
        return dest.exists()
