from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from usb_recovery.constants import APP_NAME, APP_VERSION
from usb_recovery.util import isoformat


def write_json_report(
    path: Path,
    session: dict[str, Any],
    candidates: list[dict[str, Any]],
    events: list[dict[str, Any]],
    extra: dict[str, Any] | None = None,
) -> Path:
    payload = {
        "application": APP_NAME,
        "version": APP_VERSION,
        "generated_at": isoformat(),
        "disclaimer": "Recovery is not guaranteed. Confidence scores are heuristics, not probabilities.",
        "session": session,
        "candidates": candidates,
        "events": events,
        "extra": extra or {},
    }
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path
