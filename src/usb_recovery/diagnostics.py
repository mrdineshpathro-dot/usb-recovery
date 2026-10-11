"""Sanitized / redacted support-bundle export (features 200, 260). No recovered file contents."""

from __future__ import annotations

import json
import platform
import re
import sys
from pathlib import Path

from usb_recovery.constants import APP_NAME, APP_VERSION
from usb_recovery.util import isoformat

SERIAL_RE = re.compile(r"(serial|uuid|guid)\s*[:=]\s*\S+", re.I)
HOME_RE = re.compile(r"/home/[^/\s]+")
WINUSER_RE = re.compile(r"C:\\Users\\[^\\]+", re.I)


def redact_text(text: str) -> str:
    text = SERIAL_RE.sub(r"\1=<redacted>", text)
    text = HOME_RE.sub("/home/<user>", text)
    text = WINUSER_RE.sub(r"C:\\Users\\<user>", text)
    return text


def collect_diagnostics(log_file: Path | None = None) -> dict:
    return {
        "application": APP_NAME,
        "version": APP_VERSION,
        "generated_at": isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "executable": sys.executable,
        "log_file": str(log_file) if log_file else None,
        "note": "Redacted bundle: no recovered file contents, serials, or home-directory names.",
    }


def write_support_bundle(
    dest: Path,
    log_file: Path | None = None,
    *,
    extra: dict | None = None,
    redact: bool = True,
) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = collect_diagnostics(log_file)
    if extra:
        payload["extra"] = extra
    if log_file and log_file.exists():
        text = log_file.read_text(encoding="utf-8", errors="replace")
        tail = "\n".join(text.splitlines()[-400:])
        payload["log_tail"] = redact_text(tail) if redact else tail
    text = json.dumps(payload, indent=2)
    if redact:
        text = redact_text(text)
    dest.write_text(text, encoding="utf-8")
    return dest
