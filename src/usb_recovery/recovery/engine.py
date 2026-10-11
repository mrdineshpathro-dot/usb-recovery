"""Scan + recover orchestration. Never writes to the source."""

from __future__ import annotations

import threading
from pathlib import Path

from usb_recovery.carving.carver import carve_source
from usb_recovery.config import AppConfig
from usb_recovery.images.offset import OffsetSource
from usb_recovery.workspace.exclusions import apply_exclusions
from usb_recovery.db.store import SessionStore
from usb_recovery.devices.base import ReadOnlySource
from usb_recovery.exceptions import CancelledError
from usb_recovery.filesystems.exfat import scan_exfat
from usb_recovery.filesystems.fat import scan_fat
from usb_recovery.filesystems.identifier import identify_boot_sector
from usb_recovery.filesystems.ntfs import scan_ntfs
from usb_recovery.logging_config import get_logger
from usb_recovery.models import (
    Candidate,
    DeviceInfo,
    ProgressCallback,
    ProgressEvent,
    RecoveryResult,
    ScanOptions,
)
from usb_recovery.output.destination import check_destination, verify_destination
from usb_recovery.output.naming import apply_template, resolve_collision
from usb_recovery.output.sidecars import write_sidecar
from usb_recovery.output.transaction import write_transactional
from usb_recovery.partitions.map import analyze_partitions, unallocated_ranges
from usb_recovery.reconstruct.matching import match_candidates
from usb_recovery.recovery.confidence import annotate, deduplicate
from usb_recovery.recovery.verify import result_from_file
from usb_recovery.safety import assert_destination_safe
from usb_recovery.security.scanner import suspicious_warning
from usb_recovery.util import safe_filename, unique_path

log = get_logger("engine")


def _emit(progress: ProgressCallback | None, **kwargs: object) -> None:
    if progress:
        progress(ProgressEvent(**kwargs))  # type: ignore[arg-type]


def scan_source(
    source: ReadOnlySource,
    options: ScanOptions,
    *,
    store: SessionStore | None = None,
    session_id: str | None = None,
    device: DeviceInfo | None = None,
    progress: ProgressCallback | None = None,
    cancel: threading.Event | None = None,
) -> list[Candidate]:
    def _check() -> None:
        if cancel is not None and cancel.is_set():
            raise CancelledError("scan cancelled")

    if options.image_offset:
        source = OffsetSource(source, options.image_offset)
        source.open()

    _emit(progress, phase="partitions", current=0, total=3, message="Analyzing partition tables")
    pmap = analyze_partitions(source)
    if store and session_id:
        store.save_partitions(session_id, pmap.partitions)
        store.event(session_id, "INFO", "scan", f"scheme={pmap.scheme} partitions={len(pmap.partitions)}")
        if device:
            store.save_device(session_id, device)

    candidates: list[Candidate] = []
    parts = pmap.partitions or []
    if options.partition_index is not None:
        parts = [p for p in parts if p.index == options.partition_index]

    if options.sector_range:
        start, end = options.sector_range
        # Restrict work to a user-defined byte range (feature 036).
        range_start = start * source.sector_size
        range_end = end * source.sector_size

        def in_range(offset: int) -> bool:
            return range_start <= offset < range_end
    else:
        def in_range(offset: int) -> bool:  # noqa: E306
            return True

    for i, part in enumerate(parts):
        _check()
        vol_off = part.start_lba * source.sector_size
        boot = source.read(vol_off, 4096)
        kind = identify_boot_sector(boot) or identify_boot_sector(boot[:512])
        part.filesystem = kind
        _emit(
            progress,
            phase="metadata",
            current=i,
            total=max(1, len(parts)),
            message=f"Filesystem metadata ({kind or 'unknown'}) at LBA {part.start_lba}",
        )
        if not options.enable_metadata:
            continue
        if kind in {"fat12", "fat16", "fat32"}:
            result = scan_fat(source, vol_off, include_existing=True)
            if result:
                for cand in result.candidates:
                    cand.partition_index = part.index
                    candidates.append(cand)
        elif kind == "exfat":
            result_x = scan_exfat(source, vol_off, include_existing=True)
            if result_x:
                for cand in result_x.candidates:
                    cand.partition_index = part.index
                    candidates.append(cand)
        elif kind == "ntfs":
            result_n = scan_ntfs(source, vol_off, include_existing=False)
            if result_n:
                for cand in result_n.candidates:
                    cand.partition_index = part.index
                    candidates.append(cand)
                if store and session_id:
                    for note in result_n.notes:
                        store.event(session_id, "INFO", "ntfs", note)
        elif kind == "ext":
            if store and session_id:
                store.event(
                    session_id,
                    "INFO",
                    "ext",
                    "ext2/3/4 signature detected; full inode recovery is not implemented in this MVP",
                )

    if options.enable_carving:
        _check()
        regions: list[tuple[int, int]]
        if options.full_image_carve or options.profile == "deep":
            regions = [(0, source.size)]
        elif options.enable_unallocated:
            gaps = unallocated_ranges(source, pmap.partitions)
            regions = [(start * source.sector_size, count * source.sector_size) for start, count in gaps]
            # Also carve inside volumes: deleted data often sits in "allocated" clusters
            # whose FAT entries were cleared. Standard profile carves each partition too.
            if options.profile in {"standard", "deep"}:
                for part in parts:
                    regions.append((part.start_lba * source.sector_size, part.size_bytes))
            if not regions:
                regions = [(0, source.size)]
        else:
            regions = []
        if options.sector_range:
            start, end = options.sector_range
            regions = [(start * source.sector_size, (end - start) * source.sector_size)]
        _emit(progress, phase="carve", current=0, total=1, message="Signature carving")
        carved = carve_source(
            source,
            options,
            regions=regions,
            progress=progress,
            cancel=cancel,
            signature_ids=options.signatures,
        )
        candidates.extend(carved)

    candidates = [c for c in candidates if in_range(c.source_offset)]
    candidates = [annotate(c) for c in candidates]
    if options.deduplicate:
        candidates = deduplicate(candidates)

    if options.exclude_types or options.exclude_paths:
        candidates = apply_exclusions(
            candidates, types=options.exclude_types, paths=options.exclude_paths
        )
    matches = match_candidates(candidates)
    if matches:
        for cand in candidates:
            related = [g for g in matches if cand.id in g.get("ids", [])]
            if related:
                cand.extra["matches"] = related
    if store and session_id:
        store.add_candidates(session_id, candidates)
        store.set_status(session_id, "scanned")
        store.event(session_id, "INFO", "scan", f"candidates={len(candidates)} matches={len(matches)}")
    _emit(progress, phase="done", current=1, total=1, message=f"Found {len(candidates)} candidates")
    return candidates


def recover_candidates(
    source: ReadOnlySource,
    candidates: list[Candidate],
    destination: str | Path,
    *,
    config: AppConfig | None = None,
    store: SessionStore | None = None,
    session_id: str | None = None,
    allow_same_device: bool = False,
    recreate_hierarchy: bool | None = None,
    progress: ProgressCallback | None = None,
    cancel: threading.Event | None = None,
    filename_template: str | None = None,
    collision_strategy: str = "increment",
    write_sidecars: bool = False,
    verify_dest: bool = False,
) -> list[RecoveryResult]:
    cfg = config or AppConfig()
    dest_root = Path(destination)
    needed = sum(max(0, c.size) for c in candidates)
    largest = max((c.size for c in candidates), default=0)
    assert_destination_safe(
        source.path,
        dest_root,
        needed_bytes=needed,
        prevent_same_device=cfg.prevent_same_device,
        allow_same_device=allow_same_device,
    )
    dest_root.mkdir(parents=True, exist_ok=True)
    compat = check_destination(dest_root, needed_bytes=needed, largest_file=largest)
    if not compat["ok"]:
        from usb_recovery.exceptions import DestinationError

        raise DestinationError("; ".join(compat["issues"]))
    if verify_dest:
        verify_destination(dest_root)
    recreate = cfg.recreate_directory_hierarchy if recreate_hierarchy is None else recreate_hierarchy
    results: list[RecoveryResult] = []
    for i, cand in enumerate(candidates):
        if cancel is not None and cancel.is_set():
            raise CancelledError("recovery cancelled")
        _emit(
            progress,
            phase="recover",
            current=i,
            total=len(candidates),
            message=f"Recovering {cand.name}",
        )
        rel = Path()
        if recreate and cand.original_path:
            parent = Path(cand.original_path.lstrip("/\\")).parent
            if str(parent) not in {".", ""}:
                rel = Path(*[safe_filename(p) for p in parent.parts])
        folder = dest_root / rel
        raw_name = (
            apply_template(filename_template, cand, index=i)
            if filename_template
            else safe_filename(cand.name)
        )
        if cfg.no_overwrite:
            target = resolve_collision(
                folder, raw_name, strategy=collision_strategy, digest=cand.sha256, template=cfg.collision_template
            )
            if collision_strategy == "skip" and (folder / raw_name).exists():
                result = RecoveryResult(
                    candidate_id=cand.id,
                    dest_path=str(folder / raw_name),
                    status="skipped",
                    bytes_written=0,
                    sha256=None,
                    error="destination exists",
                )
                results.append(result)
                if store and session_id:
                    store.record_recovery(session_id, result)
                continue
        else:
            target = folder / raw_name
        content: bytes = b""
        extra_content = cand.extra.get("content")
        if isinstance(extra_content, (bytes, bytearray)):
            content = bytes(extra_content)
        elif cand.size > 0 and cand.source_offset >= 0:
            content = source.read(cand.source_offset, cand.size)
        flags = suspicious_warning(cand, content[:16] if content else None)
        if flags:
            cand.notes.extend(flags)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            write_transactional(target, content)
        except OSError as exc:
            result = RecoveryResult(
                candidate_id=cand.id,
                dest_path=None,
                status="failed",
                bytes_written=0,
                sha256=None,
                error=str(exc),
            )
            results.append(result)
            if store and session_id:
                store.record_recovery(session_id, result)
            continue
        result = result_from_file(
            cand.id,
            target,
            expected_size=cand.size if cand.size else len(content),
            expected_sha256=cand.sha256 if cfg.hash_recovered else None,
            compute_hash=cfg.hash_recovered,
        )
        if write_sidecars:
            write_sidecar(target, candidate=cand, result=result)
        results.append(result)
        if store and session_id:
            store.record_recovery(session_id, result)
    if store and session_id:
        store.set_status(session_id, "recovered")
        recovered = sum(1 for r in results if r.status == "recovered")
        store.event(session_id, "INFO", "recover", f"recovered={recovered} total={len(results)}")
    return results
