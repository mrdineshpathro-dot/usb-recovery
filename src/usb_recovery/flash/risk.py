"""Acquisition risk summary — observable facts only (228). Never predicts failure."""

from __future__ import annotations

from typing import Any

from usb_recovery.models import DeviceInfo, ImagingResult


def acquisition_risk_summary(
    info: DeviceInfo | None = None,
    *,
    imaging: ImagingResult | None = None,
    stalls: int = 0,
    mounted: bool | None = None,
) -> dict[str, Any]:
    facts: list[str] = []
    if info:
        if mounted is None:
            mounted = bool(info.mountpoints)
        if mounted:
            facts.append("Source volume is mounted.")
        if info.is_physical:
            facts.append("Source is a live physical device, not a frozen image.")
        for warn in info.warnings:
            facts.append(f"{warn.severity}: {warn.message}")
    bad = len(imaging.bad_sectors) if imaging else 0
    if bad:
        facts.append(f"{bad} unreadable regions were recorded during imaging.")
    if stalls:
        facts.append(f"{stalls} throughput stall(s) observed.")
    if imaging and imaging.cancelled:
        facts.append("Acquisition was cancelled or paused; a checkpoint may exist.")
    return {
        "facts": facts or ["No adverse observables recorded in this snapshot."],
        "bad_sectors": bad,
        "stalls": stalls,
        "disclaimer": (
            "This summary reports what was observed. It cannot predict whether the "
            "flash device will fail, and it is not a health warranty."
        ),
    }
