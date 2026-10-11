"""Run supported preview/parse work in a restricted child process (254)."""

from __future__ import annotations

import multiprocessing as mp
from typing import Any

from usb_recovery.carving.validators import run_validator


def _worker(payload: tuple[str | None, bytes], conn: Any) -> None:
    name, data = payload
    try:
        ok, notes = run_validator(name, data)
        conn.send({"ok": ok, "notes": notes, "error": None})
    except Exception as exc:  # noqa: BLE001 — isolate parser crashes
        conn.send({"ok": False, "notes": [], "error": type(exc).__name__})
    finally:
        conn.close()


def isolated_preview(validator_name: str | None, data: bytes, *, timeout: float = 2.0) -> dict:
    """Parse in a child process so a hostile JPEG/PNG cannot crash the UI."""
    try:
        ctx = mp.get_context("spawn")
        parent, child = ctx.Pipe(duplex=False)
        proc = ctx.Process(target=_worker, args=((validator_name, data), child), daemon=True)
        proc.start()
        child.close()
        proc.join(timeout)
        if proc.is_alive():
            proc.terminate()
            proc.join(0.5)
            return {"ok": False, "notes": ["preview worker timed out"], "isolated": True}
        if parent.poll():
            result = parent.recv()
            result["isolated"] = True
            return result
        return {"ok": False, "notes": ["no result from preview worker"], "isolated": True}
    except Exception as exc:  # pragma: no cover - sandbox without /dev/shm etc.
        ok, notes = run_validator(validator_name, data)
        return {"ok": ok, "notes": notes, "isolated": False, "fallback": type(exc).__name__}
