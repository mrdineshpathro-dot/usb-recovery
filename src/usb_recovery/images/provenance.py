"""Image provenance manifest (feature 270)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from usb_recovery.constants import APP_NAME, APP_VERSION
from usb_recovery.images.inspect import inspect_container
from usb_recovery.util import isoformat, sha256_file


def write_provenance(
    image: str | Path,
    dest: str | Path | None = None,
    *,
    settings: dict[str, Any] | None = None,
    source_path: str | None = None,
) -> Path:
    img = Path(image)
    payload = {
        "application": APP_NAME,
        "version": APP_VERSION,
        "created_at": isoformat(),
        "image": str(img),
        "source_path": source_path,
        "sha256": sha256_file(img) if img.is_file() and img.stat().st_size <= 512 * 1024 * 1024 else None,
        "container": inspect_container(img),
        "acquisition_settings": settings or {},
        "disclaimer": "Manifest of observable acquisition facts. Not a chain-of-custody certificate.",
    }
    out = Path(dest) if dest else Path(str(img) + ".provenance.json")
    out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return out
