"""Best-effort notifications. ntfy.sh-flavored: text body + optional Title/Priority/Tags headers."""
from __future__ import annotations

import logging

import httpx

from ..config import settings

log = logging.getLogger("sdoffload.notify")


def _human_bytes(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    v = float(n or 0)
    i = 0
    while v >= 1024 and i < len(units) - 1:
        v /= 1024
        i += 1
    return f"{v:.1f} {units[i]}" if i else f"{int(v)} B"


def import_finished(imp) -> None:
    """Fire-and-forget notification on terminal status."""
    url = (settings.notify_url or "").strip()
    if not url:
        return

    cam = (imp.camera_profile.name if imp.camera_profile_id and imp.camera_profile else "—")
    if imp.status == "done":
        title = f"Offload done · {cam}"
        body = (f"Import #{imp.id} ({cam})\n"
                f"{imp.files_new} new · {imp.files_skipped} skipped · {imp.files_failed} failed\n"
                f"{_human_bytes(imp.bytes_copied)} copied")
        priority = "default"
        tags = "white_check_mark"
    elif imp.status == "failed":
        title = f"Offload FAILED · {cam}"
        body = f"Import #{imp.id} failed: {imp.error or 'unknown error'}"
        priority = "high"
        tags = "warning"
    elif imp.status == "cancelled":
        title = f"Offload cancelled · {cam}"
        body = f"Import #{imp.id} cancelled by user"
        priority = "low"
        tags = "x"
    else:
        return

    headers = {"Title": title, "Priority": priority, "Tags": tags}
    try:
        httpx.post(url, content=body.encode("utf-8"), headers=headers, timeout=5)
    except httpx.HTTPError as exc:
        log.warning("notification failed (%s): %s", url, exc)
