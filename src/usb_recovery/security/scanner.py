"""Offline file safety hints and optional local scanner hook (251, 252).

Never executes recovered files. An external scanner is invoked only if the
binary exists on PATH and the user opts in.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from usb_recovery.models import Candidate
from usb_recovery.safety import refuse_destructive_command

SUSPICIOUS_EXT = {
    "exe",
    "dll",
    "scr",
    "bat",
    "cmd",
    "ps1",
    "vbs",
    "js",
    "jar",
    "msi",
    "com",
    "pif",
    "hta",
    "lnk",
}

SUSPICIOUS_MAGIC = [
    (b"MZ", "PE/DOS executable header"),
    (b"\x7fELF", "ELF executable header"),
    (b"#!/", "script shebang"),
]


def suspicious_warning(candidate: Candidate, data: bytes | None = None) -> list[str]:
    flags: list[str] = []
    ext = (candidate.extension or Path(candidate.name).suffix.lstrip(".")).lower()
    if ext in SUSPICIOUS_EXT:
        flags.append(f"Extension .{ext} is commonly executable — do not run recovered copies")
    blob = data
    if blob is None and isinstance(candidate.extra.get("content"), (bytes, bytearray)):
        blob = bytes(candidate.extra["content"][:16])
    if blob:
        for magic, label in SUSPICIOUS_MAGIC:
            if blob.startswith(magic):
                flags.append(label)
    return flags


def scan_offline(path: str | Path, *, allow_external: bool = False) -> dict:
    """If ClamAV `clamscan` is installed and allow_external is True, run it read-only.

    Default is a local heuristic only. The file is never executed.
    """
    target = Path(path)
    if not target.is_file():
        return {"ok": False, "reason": "not a file", "engine": "none"}
    data = target.read_bytes()[:4096]
    dummy = Candidate(
        id="local",
        name=target.name,
        size=target.stat().st_size,
        file_type=target.suffix.lstrip("."),
        mime="application/octet-stream",
        method="carved",
        status="carved",
        source_offset=0,
        confidence=0,
        extension=target.suffix.lstrip("."),
    )
    flags = suspicious_warning(dummy, data)
    if not allow_external:
        return {"ok": True, "engine": "heuristic", "flags": flags, "external": False}
    clam = shutil.which("clamscan")
    if not clam:
        return {"ok": True, "engine": "heuristic", "flags": flags, "external": False, "note": "clamscan not installed"}
    cmd = f"{clam} --no-summary --stdout {target}"
    refuse_destructive_command(cmd)
    # argv list — no shell.
    try:
        proc = subprocess.run(  # noqa: S603 — argv, shell=False
            [clam, "--no-summary", "--stdout", str(target)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "engine": "clamscan", "flags": flags, "error": str(exc)}
    return {
        "ok": proc.returncode in {0, 1},
        "engine": "clamscan",
        "flags": flags,
        "external": True,
        "returncode": proc.returncode,
        "output": (proc.stdout or proc.stderr)[:2000],
    }
