"""Pre-recovery assessment and effort estimation (204, 205)."""

from __future__ import annotations

from pathlib import Path

from usb_recovery.devices.base import ReadOnlySource
from usb_recovery.devices.detector import describe_source, open_source
from usb_recovery.exceptions import ConfirmationRequired, SourceAccessError
from usb_recovery.filesystems.identifier import identify_boot_sector
from usb_recovery.models import Assessment, DeviceInfo, ScanProfile
from usb_recovery.partitions.map import analyze_partitions
from usb_recovery.safety import destination_free_bytes
from usb_recovery.util import human_size


def assess_source(
    path: str,
    *,
    confirm: str | None = None,
    probe_filesystems: bool = True,
) -> Assessment:
    risks: list[str] = []
    notes: list[str] = []
    filesystems: list[str] = []
    accessible = False
    info: DeviceInfo | None = None
    try:
        info = describe_source(path, confirm=confirm)
        accessible = True
    except ConfirmationRequired:
        risks.append("Physical device requires explicit confirmation before opening.")
        info = None
    except SourceAccessError as exc:
        risks.append(str(exc))
        info = None
    except OSError as exc:
        risks.append(f"OS error probing source: {exc}")

    size = info.size_bytes if info else 0
    sector = info.sector_size if info else 512
    mounted = bool(info.mountpoints) if info else False
    if mounted:
        risks.append("Volume is mounted; the OS may write despite a read-only handle.")
    if info:
        for warn in info.warnings:
            (risks if warn.severity != "info" else notes).append(warn.message)

    if accessible and probe_filesystems and info:
        source: ReadOnlySource | None = None
        try:
            source = open_source(path, confirm=confirm, sector_size=info.sector_size)
            pmap = analyze_partitions(source)
            notes.append(f"Partition scheme: {pmap.scheme}")
            for part in pmap.partitions:
                boot = source.read(part.start_lba * source.sector_size, 4096)
                kind = identify_boot_sector(boot) or identify_boot_sector(boot[:512])
                if kind:
                    filesystems.append(kind)
                    part.filesystem = kind
            notes.extend(pmap.notes)
        except ConfirmationRequired:
            risks.append("Filesystem probe skipped: confirmation token missing.")
        except Exception as exc:
            notes.append(f"Filesystem probe incomplete: {exc}")
        finally:
            if source is not None:
                source.close()

    profile: ScanProfile = "standard"
    if not filesystems:
        profile = "deep"
        notes.append("No filesystem identified; a carving-heavy profile may be required.")
    if any("failing" in r.lower() or "unreadable" in r.lower() for r in risks):
        profile = "quick"
    if mounted:
        profile = "quick"

    return Assessment(
        source_path=str(Path(path)),
        accessible=accessible,
        is_image=bool(info.is_image) if info else Path(path).is_file(),
        is_physical=bool(info.is_physical) if info else False,
        size_bytes=size,
        sector_size=sector,
        filesystems=sorted(set(filesystems)),
        mounted=mounted,
        risks=risks,
        recommended_profile=profile,
        notes=notes,
    )


def estimate_effort(
    assessment: Assessment,
    *,
    bytes_per_sec: float = 40_000_000,
    dest: str | None = None,
    profile: ScanProfile | None = None,
) -> Assessment:
    """Estimate time from a measured or assumed throughput. Not a promise."""
    speed = max(1.0, bytes_per_sec)
    size = max(0, assessment.size_bytes)
    chosen = profile or assessment.recommended_profile
    scan_factor = {"quick": 0.15, "standard": 0.7, "deep": 1.2}.get(chosen, 0.7)
    assessment.estimated_image_s = size / speed if size else 0.0
    assessment.estimated_scan_s = (size / speed) * scan_factor
    # Destination: image copy plus a conservative recovered-file budget (10% of source).
    assessment.estimated_dest_bytes = size + max(size // 10, 64 * 1024 * 1024) if size else 0
    if dest:
        try:
            free = destination_free_bytes(dest)
            if assessment.estimated_dest_bytes and free < assessment.estimated_dest_bytes:
                assessment.risks.append(
                    f"Destination free space {human_size(free)} is below the "
                    f"{human_size(assessment.estimated_dest_bytes)} effort estimate"
                )
        except Exception as exc:
            assessment.notes.append(f"Could not measure destination space: {exc}")
    assessment.notes.append(
        f"Effort uses {human_size(int(speed))}/s throughput (measured or default). "
        "Failing flash is often much slower."
    )
    return assessment
