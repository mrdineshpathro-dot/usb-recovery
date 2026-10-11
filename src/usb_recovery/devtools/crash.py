"""Crash-recovery self-test (304)."""

from __future__ import annotations

from pathlib import Path

from usb_recovery.imaging.dd import checkpoint_path_for, load_checkpoint
from usb_recovery.workspace.plan import save_scan_checkpoint


def crash_self_test(tmp: Path) -> dict:
    """Write checkpoints, pretend the process died, then load them back."""
    dest = tmp / "image.dd"
    tmp.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"\x00" * 1024)
    ckpt = checkpoint_path_for(dest)
    ckpt.write_text(
        '{"source_path": "x", "source_size": 1024, "offset": 512, "bad_sectors": []}',
        encoding="utf-8",
    )
    loaded = load_checkpoint(ckpt)
    scan_ckpt = tmp / "scan.checkpoint.json"
    save_scan_checkpoint(scan_ckpt, session_id="sess-test", offset=2048, extra={"phase": "carve"})
    scan = __import__("json").loads(scan_ckpt.read_text(encoding="utf-8"))
    return {
        "imaging_restored": bool(loaded and loaded.get("offset") == 512),
        "scan_restored": scan.get("offset") == 2048,
        "ok": bool(loaded) and scan.get("session_id") == "sess-test",
    }
