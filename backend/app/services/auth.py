"""Single-password UI auth: HMAC-signed session cookie.

If `settings.ui_password` is empty, auth is disabled — every request passes through.
The signing secret is generated once and persisted in the `app_settings` table so
sessions survive restarts.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from base64 import urlsafe_b64decode, urlsafe_b64encode
from time import time

from .. import models
from ..config import settings
from ..db import session_scope

COOKIE_NAME = "sdoffload_session"
SESSION_TTL = 60 * 60 * 24 * 7  # 7 days


def _b64e(b: bytes) -> str:
    return urlsafe_b64encode(b).decode().rstrip("=")


def _b64d(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return urlsafe_b64decode(s + pad)


def auth_required() -> bool:
    return bool(settings.ui_password)


def get_secret() -> str:
    if settings.auth_secret:
        return settings.auth_secret
    with session_scope() as s:
        row = s.query(models.AppSetting).filter_by(key="auth_secret").one_or_none()
        if row and row.value:
            return row.value
        secret = secrets.token_hex(32)
        if row:
            row.value = secret
        else:
            s.add(models.AppSetting(key="auth_secret", value=secret))
        return secret


def issue_token() -> str:
    ts_bytes = str(int(time())).encode()
    sig = hmac.new(get_secret().encode(), ts_bytes, hashlib.sha256).digest()
    return f"{_b64e(ts_bytes)}.{_b64e(sig)}"


def verify_token(token: str) -> bool:
    if not token:
        return False
    try:
        ts_b64, sig_b64 = token.split(".", 1)
        ts_bytes = _b64d(ts_b64)
        sig = _b64d(sig_b64)
        expected = hmac.new(get_secret().encode(), ts_bytes, hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expected):
            return False
        ts = int(ts_bytes.decode())
        return (time() - ts) < SESSION_TTL
    except Exception:
        return False


def check_password(password: str) -> bool:
    expected = settings.ui_password
    if not expected:
        return True
    return hmac.compare_digest(password.encode(), expected.encode())
