"""Per-file recovery manifest sidecars (feature 234)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from usb_recovery.models import Candidate, RecoveryResult
from usb_recovery.util import isoformat


def sidecar_path(dest: Path) -> Path:
    return dest.with_name(dest.name + ".recovery.json")


def write_sidecar(
    dest: Path,
    *,
    candidate: Candidate | None = None,
    result: RecoveryResult | None = None,
    extra: dict[str, Any] | None = None,
) -> Path:
    payload: dict[str, Any] = {
        "generated_at": isoformat(),
        "recovered_path": str(dest),
        "disclaimer": "Sidecar metadata only. Recovery is not guaranteed.",
    }
    if candidate:
        payload.update(
            {
                "candidate_id": candidate.id,
                "original_name": candidate.name,
                "original_path": candidate.original_path,
                "source_offset": candidate.source_offset,
                "method": candidate.method,
                "status": candidate.status,
                "confidence": candidate.confidence,
                "confidence_reasons": candidate.confidence_reasons,
                "source_sha256": candidate.sha256,
            }
        )
    if result:
        payload.update(
            {
                "recovery_status": result.status,
                "bytes_written": result.bytes_written,
                "recovered_sha256": result.sha256,
                "size_match": result.size_match,
                "error": result.error,
            }
        )
    if extra:
        payload["extra"] = extra
    path = sidecar_path(dest)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
