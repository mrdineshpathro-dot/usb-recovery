"""Recoverable vs unrecoverable summary and optional second copy (239, 240)."""

from __future__ import annotations

import shutil
from pathlib import Path

from usb_recovery.exceptions import SafetyError
from usb_recovery.models import RecoveryResult
from usb_recovery.safety import assert_destination_safe


def recoverable_summary(results: list[RecoveryResult]) -> dict:
    recovered = [r for r in results if r.status == "recovered"]
    partial = [r for r in results if r.status == "partial"]
    failed = [r for r in results if r.status in {"failed", "skipped"}]
    return {
        "recovered": len(recovered),
        "partial": len(partial),
        "unrecoverable": len(failed),
        "total": len(results),
        "unrecoverable_detail": [
            {"id": r.candidate_id, "status": r.status, "error": r.error} for r in failed
        ],
        "partial_detail": [
            {"id": r.candidate_id, "path": r.dest_path, "size_match": r.size_match} for r in partial
        ],
        "note": "Unrecoverable means this attempt could not write a verified copy; the source was not modified.",
    }


def copy_verified_second(
    results: list[RecoveryResult],
    second_dest: str | Path,
    *,
    source_path: str,
    confirm: bool,
    allow_same_device: bool = False,
) -> list[dict]:
    if not confirm:
        raise SafetyError("Second copy requires explicit approval (confirm=True)")
    dest = Path(second_dest)
    dest.mkdir(parents=True, exist_ok=True)
    assert_destination_safe(source_path, dest, allow_same_device=allow_same_device)
    copied: list[dict] = []
    for item in results:
        if item.status != "recovered" or not item.dest_path:
            continue
        src = Path(item.dest_path)
        if not src.is_file():
            continue
        target = dest / src.name
        shutil.copy2(src, target)
        copied.append({"from": str(src), "to": str(target), "sha256": item.sha256})
    return copied
