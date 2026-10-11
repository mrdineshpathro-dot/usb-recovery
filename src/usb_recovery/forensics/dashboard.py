"""Recovery readiness and evidence dashboard (360)."""

from __future__ import annotations

from usb_recovery.carving.signatures import load_signatures
from usb_recovery.carving.validators import VALIDATORS
from usb_recovery.devtools.readiness import feature_readiness
from usb_recovery.forensics.pipeline import PIPELINE_VERSION
from usb_recovery.intel.plan import GOAL_SIGNATURES


KNOWN_DEFECTS = [
    "Deleted FAT 8.3 names lose the first character.",
    "Zeroed FAT chains use a contiguous heuristic marked uncertain.",
    "NTFS $LogFile is parsed for timeline context, never replayed.",
    "Dynamic/differencing VHD and full AFF4 map replay are not implemented.",
    "Carving cannot un-fragment arbitrary files.",
]


def evidence_dashboard() -> dict:
    ready = feature_readiness()
    version, sigs = load_signatures()
    return {
        "features": {
            "total": ready.get("total"),
            "counts": ready.get("counts"),
        },
        "signatures_version": version,
        "signatures": [s.id for s in sigs],
        "validators": sorted(VALIDATORS),
        "scan_goals": sorted(GOAL_SIGNATURES),
        "pipeline_version": PIPELINE_VERSION,
        "known_defects": KNOWN_DEFECTS,
        "maturity": _maturity(ready.get("counts") or {}),
        "note": "Dashboard summarizes this build. It is not a certification.",
    }


def _maturity(counts: dict) -> str:
    done = counts.get("done", 0)
    total = sum(counts.values()) or 1
    ratio = done / total
    if ratio >= 0.85:
        return "implemented-with-documented-limits"
    if ratio >= 0.5:
        return "partial"
    return "early"
