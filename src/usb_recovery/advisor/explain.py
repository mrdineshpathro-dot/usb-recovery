"""Limitation explainer, error diagnosis, failure analysis, score evidence (203, 206, 208, 210)."""

from __future__ import annotations

from typing import Any

from usb_recovery.models import Candidate, RecoveryResult
from usb_recovery.recovery.confidence import band_for

LIMITATIONS: dict[str, dict[str, str]] = {
    "overwritten": {
        "title": "Overwritten clusters / MFT records",
        "summary": (
            "Once the operating system reuses a cluster or file record, the previous "
            "bytes are gone. Metadata recovery cannot reconstruct content that was "
            "replaced. Carving only finds whatever signatures still exist in leftover regions."
        ),
        "advice": "Stop using the device. Image it. Do not expect a full original file.",
    },
    "trimmed": {
        "title": "TRIM / discard on flash",
        "summary": (
            "Many USB controllers and SSDs honour TRIM/unmap. After a format or delete, "
            "the NAND pages may already read as zeros. No software running on the host "
            "can undo a completed discard."
        ),
        "advice": "If reads return long zero runs, treat those regions as unrecoverable.",
    },
    "controller": {
        "title": "Controller-inaccessible / translator failure",
        "summary": (
            "USB sticks hide NAND behind a flash translation layer. If the controller, "
            "firmware, or mapping table fails, the host only sees I/O errors. This tool "
            "cannot reprogram a dead controller or dump raw NAND."
        ),
        "advice": "Image what still reads, then stop. Physical chip-off is out of scope.",
    },
    "formatted": {
        "title": "Quick or full format",
        "summary": (
            "A quick format typically rebuilds FAT/MFT structures but may leave file "
            "payloads. A full overwrite format does not. exFAT/NTFS quick formats often "
            "destroy directory names while leaving some payloads for carving."
        ),
        "advice": "Prefer metadata scan first, then carving. Do not write a new filesystem.",
    },
    "encrypted": {
        "title": "Hardware or BitLocker/FileVault encryption",
        "summary": (
            "Encrypted volumes look like high-entropy noise. Without the key this "
            "application cannot decrypt them. Carving will not produce usable documents."
        ),
        "advice": "Recover the key/password first. Do not confuse entropy with lost files.",
    },
    "fragmented": {
        "title": "Fragmented files without allocation metadata",
        "summary": (
            "Signature carving assumes a contiguous run after a header. Fragmented files "
            "need FAT chains or NTFS runlists. Heuristic stitching is marked uncertain."
        ),
        "advice": "Trust metadata reconstruction over carved blobs when both exist.",
    },
}

ERROR_CATALOG: list[tuple[tuple[str, ...], str, list[str]]] = [
    (
        ("permission", "eacces", "access denied", "errno 13"),
        "The OS refused to open the source. This is an access-control problem, not a damaged filesystem.",
        [
            "Linux: unmount the volume, then rerun as root or a member of group disk.",
            "Windows: run as Administrator and use \\\\.\\PhysicalDriveN or \\\\.\\E:.",
            "The application will not bypass OS permissions.",
        ],
    ),
    (
        ("no such file", "enoent", "not found"),
        "The path does not exist. The device may have been unplugged or the image moved.",
        ["Re-list devices.", "If this is a resume, verify the same device is connected (serial/size)."],
    ),
    (
        ("input/output", "eio", "errno 5", "i/o error"),
        "The device returned a read error. This is often failing flash or a loose cable, not a software bug.",
        [
            "Stop a deep scan.",
            "Try a different cable/port.",
            "Image with retries and a stop threshold; continued reads can destroy remaining data.",
        ],
    ),
    (
        ("same physical", "same-device", "same physical storage"),
        "Recovered files would have been written onto the source disk.",
        ["Choose a destination on a different drive.", "Do not use --allow-same-device on a live pen drive."],
    ),
    (
        ("confirmation", "i_understand_read_only"),
        "Physical device access requires an explicit confirmation token.",
        ["Pass --confirm I_UNDERSTAND_READ_ONLY or tick the GUI safety checkbox."],
    ),
    (
        ("no space", "enospc", "destination has"),
        "The destination filesystem does not have enough free space.",
        ["Free space or pick another disk.", "Run a destination verification test first."],
    ),
    (
        ("cancelled", "stop threshold"),
        "The operation was cancelled or paused because of a safety/error threshold.",
        ["Inspect the bad-sector map.", "Resume from the checkpoint only if the case value justifies more reads."],
    ),
]


def explain_limitations(topic: str | None = None) -> list[dict[str, str]]:
    if topic:
        key = topic.lower().strip()
        item = LIMITATIONS.get(key)
        if item:
            return [item]
        matches = [v for k, v in LIMITATIONS.items() if key in k or key in v["title"].lower()]
        return matches or list(LIMITATIONS.values())
    return list(LIMITATIONS.values())


def diagnose_error(message: str) -> dict[str, Any]:
    lowered = message.lower()
    for needles, explanation, steps in ERROR_CATALOG:
        if any(n in lowered for n in needles):
            return {
                "matched": True,
                "explanation": explanation,
                "steps": steps,
                "original": message,
            }
    return {
        "matched": False,
        "explanation": (
            "No catalog match. Treat this as an unexpected error: do not run repair "
            "or format commands against the source."
        ),
        "steps": [
            "Copy the exact error into the session log.",
            "Export a redacted diagnostic bundle.",
            "Retry against a disk image rather than the live device.",
        ],
        "original": message,
    }


def summarize_failures(results: list[RecoveryResult]) -> dict[str, Any]:
    groups: dict[str, list[str]] = {}
    for item in results:
        if item.status in {"recovered"}:
            continue
        reason = item.error or item.status
        groups.setdefault(reason, []).append(item.candidate_id)
    return {
        "failed": sum(1 for r in results if r.status == "failed"),
        "partial": sum(1 for r in results if r.status == "partial"),
        "skipped": sum(1 for r in results if r.status == "skipped"),
        "recovered": sum(1 for r in results if r.status == "recovered"),
        "by_reason": {k: {"count": len(v), "ids": v[:50]} for k, v in groups.items()},
        "note": "A failed copy never modifies the source. Incomplete outputs can be cleaned up.",
    }


def explain_score(candidate: Candidate) -> dict[str, Any]:
    band, meaning = band_for(candidate.confidence)
    evidence = list(candidate.confidence_reasons)
    if candidate.method == "metadata":
        evidence.append("Directory / $MFT record supplied the name and size")
    elif candidate.method == "carved":
        evidence.append("Only a format signature (and optional footer) was used")
    elif candidate.method == "existing":
        evidence.append("Live filesystem entry; file may still be readable without recovery")
    if candidate.is_fragmented:
        evidence.append("Allocation was non-contiguous")
    if candidate.is_duplicate:
        evidence.append("Byte-identical to another candidate")
    return {
        "id": candidate.id,
        "name": candidate.name,
        "score": candidate.confidence,
        "band": band,
        "band_meaning": meaning,
        "not_a_probability": True,
        "evidence": evidence,
        "method": candidate.method,
        "status": candidate.status,
        "offset": candidate.source_offset,
        "sha256": candidate.sha256,
    }
