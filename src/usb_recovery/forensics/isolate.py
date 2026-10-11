"""Isolated binary parser workers (358)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from usb_recovery.carving.validators import run_validator


def _src_root() -> str:
    return str(Path(__file__).resolve().parents[2])


def isolate_validate(kind: str, data: bytes, *, timeout: float = 5.0) -> dict:
    """Run a format validator in a subprocess with CPU/AS limits when available."""
    env = os.environ.copy()
    env["PYTHONPATH"] = _src_root() + os.pathsep + env.get("PYTHONPATH", "")
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "usb_recovery.forensics.isolate", kind],
            input=data,
            capture_output=True,
            timeout=timeout,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "isolated": True, "error": "timeout", "notes": ["parser worker timed out"]}
    if proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", errors="replace")[:500]
        return {"ok": False, "isolated": True, "error": err or f"exit {proc.returncode}", "notes": []}
    try:
        payload = json.loads(proc.stdout.decode("utf-8"))
    except json.JSONDecodeError:
        return {"ok": False, "isolated": True, "error": "invalid worker output", "notes": []}
    payload["isolated"] = True
    return payload


def _apply_limits() -> None:
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
        # 256 MiB address space; ignore if the platform rejects it.
        resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
    except Exception:
        return


def main(argv: list[str] | None = None) -> int:
    _apply_limits()
    args = argv if argv is not None else sys.argv[1:]
    kind = args[0] if args else ""
    data = sys.stdin.buffer.read()
    ok, notes = run_validator(kind, data)
    sys.stdout.write(json.dumps({"ok": ok, "notes": notes, "kind": kind}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
