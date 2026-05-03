"""SD Media Offload host-agent.

Invoked by udev rules with one of two subcommands:
  attach <devnode>   — block device added; mount it ro and notify the VM
  detach <devnode>   — block device removed; unmount and notify the VM

Configuration via env vars (set in /etc/default/sdoffload-agent):
  SDOFFLOAD_VM_URL      base URL of the backend  (e.g. http://10.0.0.50:8000)
  SDOFFLOAD_TOKEN       shared secret matching the backend's host_token
  SDOFFLOAD_MOUNT_BASE  parent dir for mounts    (default /mnt/sdoffload)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

import httpx


def _load_env_file(path: str = "/etc/default/sdoffload-agent") -> None:
    """udev does not inherit systemd EnvironmentFile, so load it ourselves."""
    if not os.path.isfile(path):
        return
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                v = v.strip().strip('"').strip("'")
                os.environ.setdefault(k.strip(), v)
    except OSError:
        pass


_load_env_file()

VM_URL = os.environ.get("SDOFFLOAD_VM_URL", "http://localhost:8000").rstrip("/")
TOKEN = os.environ.get("SDOFFLOAD_TOKEN", "change-me")
MOUNT_BASE = Path(os.environ.get("SDOFFLOAD_MOUNT_BASE", "/mnt/sdoffload"))
HTTP_TIMEOUT = 10.0


logging.basicConfig(
    level=os.environ.get("SDOFFLOAD_LOG_LEVEL", "INFO"),
    format="%(asctime)s sdoffload-agent %(levelname)s: %(message)s",
)
log = logging.getLogger("sdoffload-agent")


def cli() -> int:
    p = argparse.ArgumentParser(prog="sdoffload-agent")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("attach"); a.add_argument("devnode")
    d = sub.add_parser("detach"); d.add_argument("devnode")
    args = p.parse_args()
    try:
        if args.cmd == "attach":
            return on_attach(Path(args.devnode))
        if args.cmd == "detach":
            return on_detach(Path(args.devnode))
    except Exception:
        log.exception("agent error")
        return 1
    return 0


def on_attach(devnode: Path) -> int:
    info = blkid(devnode)
    if not info:
        log.warning("Skipping %s — blkid returned nothing", devnode)
        return 0

    fs_uuid = info.get("UUID")
    label = info.get("LABEL")
    fs_type = info.get("TYPE")

    mount_dir = MOUNT_BASE / (fs_uuid or devnode.name)
    mount_dir.mkdir(parents=True, exist_ok=True)

    if not is_mounted(mount_dir):
        log.info("Mounting %s ro at %s (fs=%s)", devnode, mount_dir, fs_type)
        mount_ro(devnode, mount_dir, fs_type)

    serial = usb_serial_for(devnode)
    size_bytes = device_size(devnode)

    payload = {
        "fs_uuid": fs_uuid, "serial": serial, "label": label,
        "fs_type": fs_type, "size_bytes": size_bytes,
        "mount_path": str(mount_dir),
    }
    notify("/api/host/device-attached", payload)
    return 0


def on_detach(devnode: Path) -> int:
    candidates = [d for d in MOUNT_BASE.iterdir() if d.is_dir()] if MOUNT_BASE.exists() else []
    for d in candidates:
        if is_mounted(d) and not any(d.iterdir()):
            continue
        if is_mounted(d):
            log.info("Unmounting %s", d)
            try:
                subprocess.run(["umount", str(d)], check=False)
            except Exception:
                log.exception("umount failed for %s", d)
    notify("/api/host/device-detached", {"mount_path": str(MOUNT_BASE)})
    return 0


def blkid(devnode: Path) -> dict[str, str]:
    try:
        out = subprocess.check_output(["blkid", "-o", "export", str(devnode)], text=True, timeout=5)
    except subprocess.CalledProcessError:
        return {}
    except FileNotFoundError:
        return {}
    return dict(line.split("=", 1) for line in out.splitlines() if "=" in line)


def usb_serial_for(devnode: Path) -> str | None:
    try:
        out = subprocess.check_output(
            ["udevadm", "info", "--query=property", "--name", str(devnode)],
            text=True, timeout=5,
        )
    except Exception:
        return None
    for line in out.splitlines():
        if line.startswith("ID_SERIAL_SHORT="):
            return line.split("=", 1)[1] or None
    for line in out.splitlines():
        if line.startswith("ID_SERIAL="):
            return line.split("=", 1)[1] or None
    return None


def device_size(devnode: Path) -> int | None:
    try:
        out = subprocess.check_output(["blockdev", "--getsize64", str(devnode)], text=True, timeout=5)
        return int(out.strip())
    except Exception:
        return None


def is_mounted(path: Path) -> bool:
    try:
        with open("/proc/mounts") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2 and parts[1] == str(path):
                    return True
    except Exception:
        pass
    return False


def mount_ro(devnode: Path, target: Path, fs_type: str | None) -> None:
    cmd = ["mount", "-o", "ro,nosuid,nodev,noexec"]
    if fs_type:
        cmd += ["-t", fs_type]
    cmd += [str(devnode), str(target)]
    subprocess.run(cmd, check=True)


def notify(path: str, payload: dict) -> None:
    url = VM_URL + path
    headers = {"X-Host-Token": TOKEN}
    try:
        r = httpx.post(url, json=payload, headers=headers, timeout=HTTP_TIMEOUT)
        log.info("Notified %s -> %s", url, r.status_code)
        if r.status_code >= 400:
            log.warning("Backend response: %s", r.text[:300])
    except httpx.HTTPError as exc:
        log.error("Failed to notify backend: %s (payload=%s)", exc, json.dumps(payload))


if __name__ == "__main__":
    sys.exit(cli())
