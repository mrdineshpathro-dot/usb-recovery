"""Scan plan builder and selective rescan (281, 282, 289)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from usb_recovery.models import ScanOptions, ScanProfile
from usb_recovery.util import isoformat, new_id


@dataclass
class ScanPlan:
    id: str
    profile: ScanProfile = "standard"
    filesystems: list[str] = field(default_factory=list)
    signatures: list[str] = field(default_factory=list)
    regions: list[tuple[int, int]] = field(default_factory=list)  # LBA start, end
    exclude_types: list[str] = field(default_factory=list)
    exclude_paths: list[str] = field(default_factory=list)
    image_offset: int = 0
    notes: str = ""

    def to_options(self) -> ScanOptions:
        options = ScanOptions.from_profile(self.profile)
        options.signatures = self.signatures or None
        if self.regions:
            start, end = self.regions[0]
            options.sector_range = (start, end)
        return options

    def to_dict(self) -> dict:
        data = asdict(self)
        data["regions"] = [list(r) for r in self.regions]
        return data


def build_plan(
    *,
    profile: ScanProfile = "standard",
    filesystems: list[str] | None = None,
    signatures: list[str] | None = None,
    regions: list[tuple[int, int]] | None = None,
    exclude_types: list[str] | None = None,
    image_offset: int = 0,
) -> ScanPlan:
    return ScanPlan(
        id=new_id("plan-"),
        profile=profile,
        filesystems=filesystems or [],
        signatures=signatures or [],
        regions=regions or [],
        exclude_types=exclude_types or [],
        image_offset=image_offset,
    )


def save_plan(plan: ScanPlan, path: Path) -> Path:
    payload = {"saved_at": isoformat(), **plan.to_dict()}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def load_plan(path: Path) -> ScanPlan:
    data = json.loads(path.read_text(encoding="utf-8"))
    regions = [tuple(r) for r in data.get("regions") or []]
    return ScanPlan(
        id=data.get("id") or new_id("plan-"),
        profile=data.get("profile") or "standard",
        filesystems=data.get("filesystems") or [],
        signatures=data.get("signatures") or [],
        regions=regions,  # type: ignore[arg-type]
        exclude_types=data.get("exclude_types") or [],
        exclude_paths=data.get("exclude_paths") or [],
        image_offset=int(data.get("image_offset") or 0),
        notes=data.get("notes") or "",
    )


def save_scan_checkpoint(path: Path, *, session_id: str, offset: int, extra: dict | None = None) -> Path:
    payload = {"session_id": session_id, "offset": offset, "saved_at": isoformat(), "extra": extra or {}}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
