"""Versioned file-signature database (feature 062 / 188)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Iterable


def _hex_to_bytes(value: str | None) -> bytes | None:
    if not value:
        return None
    return bytes.fromhex(value)


@dataclass(frozen=True)
class FileSignature:
    id: str
    name: str
    mime: str
    extensions: tuple[str, ...]
    header: bytes
    header_offset: int = 0
    footer: bytes | None = None
    max_size: int = 64 * 1024 * 1024
    validator: str | None = None


def load_signatures(path: Path | None = None) -> tuple[int, list[FileSignature]]:
    if path is None:
        with resources.files("usb_recovery.data").joinpath("signatures.json").open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    else:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    version = int(payload.get("version", 1))
    sigs: list[FileSignature] = []
    for item in payload.get("signatures", []):
        header = _hex_to_bytes(item.get("header_hex"))
        if not header:
            continue
        sigs.append(
            FileSignature(
                id=item["id"],
                name=item["name"],
                mime=item["mime"],
                extensions=tuple(item.get("extensions") or []),
                header=header,
                header_offset=int(item.get("header_offset") or 0),
                footer=_hex_to_bytes(item.get("footer_hex")),
                max_size=int(item.get("max_size") or 64 * 1024 * 1024),
                validator=item.get("validator"),
            )
        )
    return version, sigs


def filter_signatures(sigs: Iterable[FileSignature], ids: list[str] | None) -> list[FileSignature]:
    if not ids:
        return list(sigs)
    wanted = {item.lower() for item in ids}
    return [s for s in sigs if s.id.lower() in wanted or any(ext in wanted for ext in s.extensions)]
