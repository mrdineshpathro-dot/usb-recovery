"""USB connection diagnostics and safe reconnection identity (224, 225)."""

from __future__ import annotations

from typing import Any

from usb_recovery.exceptions import IdentityMismatchError
from usb_recovery.flash.usbids import lookup_usb
from usb_recovery.models import DeviceInfo, ImagingResult


def identity_from_device(info: DeviceInfo) -> dict[str, Any]:
    return {
        "path": info.path,
        "vendor": info.vendor,
        "model": info.model,
        "serial": info.serial,
        "size_bytes": info.size_bytes,
        "bus": info.bus,
        "is_image": info.is_image,
    }


def identities_match(expected: dict[str, Any], actual: dict[str, Any]) -> tuple[bool, list[str]]:
    issues: list[str] = []
    if expected.get("is_image") or actual.get("is_image"):
        if expected.get("size_bytes") != actual.get("size_bytes"):
            issues.append("image size changed")
        return not issues, issues
    for key in ("serial", "size_bytes"):
        if expected.get(key) and actual.get(key) and expected.get(key) != actual.get(key):
            issues.append(f"{key} mismatch: {expected.get(key)!r} vs {actual.get(key)!r}")
    if expected.get("vendor") and actual.get("vendor") and expected["vendor"] != actual["vendor"]:
        issues.append("vendor mismatch")
    if expected.get("model") and actual.get("model") and expected["model"] != actual["model"]:
        issues.append("model mismatch")
    return not issues, issues


def assert_same_device(expected: dict[str, Any], actual: dict[str, Any]) -> None:
    ok, issues = identities_match(expected, actual)
    if not ok:
        raise IdentityMismatchError(
            "Reconnected device does not match the checkpoint identity: " + "; ".join(issues)
        )


def diagnose_connection(
    info: DeviceInfo,
    *,
    io_errors: int = 0,
    stalls: int = 0,
) -> dict[str, Any]:
    usb = lookup_usb(info.extra.get("usb_vid"), info.extra.get("usb_pid"))
    clues: list[str] = []
    if info.mountpoints:
        clues.append("Filesystem is mounted — OS writes are possible; this is not a cable fault.")
    if io_errors and stalls:
        clues.append(
            "Both I/O errors and throughput stalls: try another cable and port before a deep scan."
        )
    elif io_errors and not info.warnings:
        clues.append("Read errors without mount warnings often indicate flash or bridge failure.")
    elif stalls and not io_errors:
        clues.append("Stalls without EIO can be a power/USB enumeration issue rather than a bad FAT.")
    if not clues:
        clues.append("No connection instability observed in this snapshot.")
    return {
        "identity": identity_from_device(info),
        "usb_lookup": usb,
        "io_errors": io_errors,
        "stalls": stalls,
        "clues": clues,
        "note": "These clues distinguish cabling from filesystem damage; they are not a diagnosis of NAND health.",
    }
