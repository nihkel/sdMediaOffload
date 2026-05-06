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
import logging.handlers
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

# udev discards stderr/stdout of RUN+= commands. Send to syslog so the events
# show up in `journalctl -t sdoffload-agent` for both interactive and udev runs.
try:
    _syslog = logging.handlers.SysLogHandler(address="/dev/log")
    _syslog.ident = "sdoffload-agent: "
    _syslog.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    logging.getLogger().addHandler(_syslog)
except Exception:
    pass


def cli() -> int:
    p = argparse.ArgumentParser(prog="sdoffload-agent")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("attach"); a.add_argument("devnode")
    d = sub.add_parser("detach"); d.add_argument("devnode")
    ai = sub.add_parser("attach-iphone"); ai.add_argument("udid")
    di = sub.add_parser("detach-iphone"); di.add_argument("udid")
    sub.add_parser("serve")
    args = p.parse_args()
    try:
        if args.cmd == "attach":
            return on_attach(Path(args.devnode))
        if args.cmd == "detach":
            return on_detach(Path(args.devnode))
        if args.cmd == "attach-iphone":
            return on_attach_iphone(args.udid)
        if args.cmd == "detach-iphone":
            return on_detach_iphone(args.udid)
        if args.cmd == "serve":
            return run_server()
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


def on_attach_iphone(udid: str) -> int:
    """Mount a paired iPhone (libimobiledevice + ifuse) and notify the backend."""
    if not udid:
        log.warning("attach-iphone called without UDID")
        return 0

    # Confirm the device is visible to libimobiledevice (paired & trusted)
    try:
        listed = subprocess.check_output(["idevice_id", "-l"], text=True, timeout=5).split()
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as exc:
        log.warning("idevice_id failed (%s); is libimobiledevice installed and is the phone paired?", exc)
        return 0
    if udid not in listed:
        log.info("iPhone %s not visible (idevice_id list: %s); skipping", udid, listed)
        return 0

    try:
        name = subprocess.check_output(["idevicename", "-u", udid], text=True, timeout=5).strip()
    except Exception:
        name = f"iphone-{udid[:8]}"

    mount_dir = MOUNT_BASE / f"iphone-{udid[:8]}"
    mount_dir.mkdir(parents=True, exist_ok=True)

    if not is_mounted(mount_dir):
        log.info("Mounting iPhone %s (%s) at %s via ifuse", udid, name, mount_dir)
        try:
            subprocess.run(
                ["ifuse", "-o", "ro,allow_other", "-u", udid, str(mount_dir)],
                check=True, timeout=30,
            )
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as exc:
            log.error("ifuse mount failed: %s", exc)
            return 1

    payload = {
        "fs_uuid": udid,
        "serial": udid,
        "label": name or f"iphone-{udid[:8]}",
        "fs_type": "ifuse-afc",
        "size_bytes": None,
        "mount_path": str(mount_dir),
    }
    notify("/api/host/device-attached", payload)
    return 0


def on_detach_iphone(udid: str) -> int:
    if not udid:
        return 0
    mount_dir = MOUNT_BASE / f"iphone-{udid[:8]}"
    if is_mounted(mount_dir):
        log.info("Unmounting iPhone at %s", mount_dir)
        subprocess.run(["fusermount", "-u", str(mount_dir)], check=False)
    notify("/api/host/device-detached", {"fs_uuid": udid, "mount_path": str(mount_dir)})
    return 0


def run_server() -> int:
    """Long-running HTTP server invoked from the LXC for eject/list operations."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    listen = os.environ.get("SDOFFLOAD_LISTEN", "0.0.0.0:8901")
    host, port = listen.split(":")
    port = int(port)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            log.info("HTTP %s", fmt % args)

        def _ok_token(self):
            return self.headers.get("X-Host-Token") == TOKEN

        def _respond(self, status, body):
            payload = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):  # noqa: N802
            if self.path == "/health":
                return self._respond(200, {"ok": True})
            if not self._ok_token():
                return self._respond(401, {"error": "invalid token"})
            if self.path == "/devices":
                mounts = []
                if MOUNT_BASE.exists():
                    for d in MOUNT_BASE.iterdir():
                        if d.is_dir() and is_mounted(d):
                            mounts.append(str(d))
                return self._respond(200, {"mounted": mounts})
            return self._respond(404, {"error": "not found"})

        def do_POST(self):  # noqa: N802
            if not self._ok_token():
                return self._respond(401, {"error": "invalid token"})
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                body = json.loads(raw or b"{}")
            except json.JSONDecodeError:
                return self._respond(400, {"error": "invalid json"})

            if self.path == "/eject":
                mount_path = str(body.get("mount_path") or "").strip()
                base = str(MOUNT_BASE.resolve())
                if not mount_path or not mount_path.startswith(base + "/"):
                    return self._respond(400, {"error": f"mount_path must be under {base}/"})
                target = Path(mount_path)
                if not is_mounted(target):
                    return self._respond(200, {"ok": True, "already": "not mounted"})
                try:
                    subprocess.run(["umount", str(target)], check=True, timeout=10)
                    log.info("Ejected %s", target)
                    return self._respond(200, {"ok": True})
                except subprocess.CalledProcessError as e:
                    return self._respond(500, {"error": f"umount failed: {e}"})
                except subprocess.TimeoutExpired:
                    return self._respond(504, {"error": "umount timed out"})
            return self._respond(404, {"error": "not found"})

    log.info("Host-agent server listening on %s:%s (mount base %s)", host, port, MOUNT_BASE)
    server = ThreadingHTTPServer((host, port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(cli())
