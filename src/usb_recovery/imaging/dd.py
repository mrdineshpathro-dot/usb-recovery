"""Raw DD imaging with checkpoints, retries, and a bad-sector map.

Writes go only to the destination image file. The source is read-only.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path

from usb_recovery.config import AppConfig
from usb_recovery.devices.base import ReadOnlySource
from usb_recovery.exceptions import CancelledError, DestinationError, SafetyError, StopThresholdError
from usb_recovery.flash.adaptive import AdaptivePolicy, StabilityMonitor
from usb_recovery.flash.connection import assert_same_device
from usb_recovery.flash.heatmap import render_heatmap
from usb_recovery.logging_config import get_logger
from usb_recovery.models import BadSector, ImagingResult, ProgressCallback, ProgressEvent
from usb_recovery.safety import assert_destination_safe, warn_failing_media
from usb_recovery.util import isoformat

log = get_logger("imaging")


def checkpoint_path_for(dest: str | Path) -> Path:
    return Path(str(dest) + ".checkpoint.json")


def bad_map_path_for(dest: str | Path) -> Path:
    return Path(str(dest) + ".bad-sectors.json")


def load_checkpoint(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        log.warning("ignoring corrupt checkpoint %s", path)
        return None


def _save_checkpoint(path: Path, payload: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)


def image_source(
    source: ReadOnlySource,
    dest: str | Path,
    *,
    config: AppConfig | None = None,
    progress: ProgressCallback | None = None,
    cancel: threading.Event | None = None,
    resume: bool = True,
    allow_same_device: bool = False,
    policy: AdaptivePolicy | None = None,
    expected_identity: dict | None = None,
    current_identity: dict | None = None,
) -> ImagingResult:
    cfg = config or AppConfig()
    dest_path = Path(dest)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    assert_destination_safe(
        source.path,
        dest_path,
        needed_bytes=source.size,
        prevent_same_device=cfg.prevent_same_device,
        allow_same_device=allow_same_device,
    )
    if dest_path.resolve() == Path(source.path).resolve():
        raise SafetyError("Refusing to image a device onto itself")

    ckpt_file = checkpoint_path_for(dest_path)
    start_offset = 0
    resumed = False
    bad: list[BadSector] = []
    ident = current_identity
    if resume:
        ckpt = load_checkpoint(ckpt_file)
        if ckpt and ckpt.get("source_size") == source.size:
            stored_id = ckpt.get("identity")
            if stored_id and current_identity:
                assert_same_device(stored_id, current_identity)
            elif stored_id and expected_identity:
                assert_same_device(stored_id, expected_identity)
            if ckpt.get("source_path") == source.path or stored_id:
                start_offset = int(ckpt.get("offset") or 0)
                resumed = start_offset > 0
                for item in ckpt.get("bad_sectors") or []:
                    bad.append(BadSector(**item) if not isinstance(item, BadSector) else item)
                log.info("resuming image at offset %s", start_offset)
                ident = stored_id or ident
    if expected_identity and current_identity:
        assert_same_device(expected_identity, current_identity)

    adapt = policy or AdaptivePolicy(
        base_retries=cfg.bad_sector_retries,
        base_delay_s=cfg.bad_sector_retry_delay_s,
        max_block=cfg.imaging_block_size,
        block_size=cfg.imaging_block_size,
    )
    monitor = StabilityMonitor()

    mode = "r+b" if dest_path.exists() and resumed else "wb"
    hasher = hashlib.sha256() if cfg.hash_while_imaging else None
    block = max(512, cfg.imaging_block_size)
    written = start_offset
    t0 = time.monotonic()

    if hasher and start_offset:
        # Re-hash already written prefix so the final digest covers the whole image.
        with open(dest_path, "rb") as existing:
            remaining = start_offset
            while remaining:
                chunk = existing.read(min(block, remaining))
                if not chunk:
                    break
                hasher.update(chunk)
                remaining -= len(chunk)

    last_checkpoint = start_offset
    cancelled = False
    try:
        with open(dest_path, mode) as out:
            if resumed:
                out.seek(start_offset)
            offset = start_offset
            while offset < source.size:
                if cancel is not None and cancel.is_set():
                    cancelled = True
                    raise CancelledError("imaging cancelled")
                adapt.check_budget()
                adapt.check_stop()
                this = min(adapt.block_size, block, source.size - offset)
                if adapt.read_budget:
                    this = min(this, max(0, adapt.read_budget - adapt.bytes_read))
                    if this == 0:
                        raise StopThresholdError("Source read budget exhausted")
                data, failures = _read_with_retries(
                    source,
                    offset,
                    this,
                    retries=adapt.retries_now(),
                    delay=adapt.delay_now(),
                    sector_size=source.sector_size,
                    policy=cfg.bad_sector_policy,
                )
                if failures:
                    adapt.on_failure()
                else:
                    adapt.on_success(len(data))
                bad.extend(failures)
                out.write(data)
                if hasher:
                    hasher.update(data)
                offset += this
                written = offset
                monitor.mark(offset)
                ckpt_payload = {
                    "source_path": source.path,
                    "source_size": source.size,
                    "dest_path": str(dest_path),
                    "offset": offset,
                    "updated_at": isoformat(),
                    "bad_sectors": [b.__dict__ for b in bad],
                    "identity": ident,
                }
                if offset - last_checkpoint >= cfg.checkpoint_every_bytes:
                    out.flush()
                    _save_checkpoint(ckpt_file, ckpt_payload)
                    last_checkpoint = offset
                if progress:
                    elapsed = max(1e-6, time.monotonic() - t0)
                    speed = (offset - start_offset) / elapsed
                    remain = (source.size - offset) / speed if speed else 0
                    progress(
                        ProgressEvent(
                            phase="image",
                            current=offset,
                            total=source.size,
                            message="Creating disk image",
                            bytes_done=offset,
                            bytes_total=source.size,
                            extra={
                                "speed_bps": speed,
                                "eta_s": remain,
                                "bad": len(bad),
                                "stability": monitor.summary(),
                            },
                        )
                    )
            out.flush()
    except CancelledError:
        _save_checkpoint(
            ckpt_file,
            {
                "source_path": source.path,
                "source_size": source.size,
                "dest_path": str(dest_path),
                "offset": written,
                "updated_at": isoformat(),
                    "bad_sectors": [b.__dict__ for b in bad],
                "cancelled": True,
                "identity": ident,
            },
        )
        raise
    except OSError as exc:
        raise DestinationError(f"Failed writing image {dest_path}: {exc}") from exc

    digest = hasher.hexdigest() if hasher else None
    if ckpt_file.exists() and not cancelled:
        ckpt_file.unlink()
    bad_path = bad_map_path_for(dest_path)
    bad_path.write_text(
        json.dumps(
            {
                "source": source.path,
                "image": str(dest_path),
                "created_at": isoformat(),
                "bad_sectors": [b.__dict__ for b in bad],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    heat = render_heatmap(bad, source.size)
    Path(str(dest_path) + ".heatmap.txt").write_text(heat["ascii"] + "\n", encoding="utf-8")
    warning = warn_failing_media(len(bad), cfg.unstable_device_bad_sector_threshold)
    if warning:
        log.warning(warning)
    log.info("image complete dest=%s sha256=%s bad=%s", dest_path, digest, len(bad))
    return ImagingResult(
        source_path=source.path,
        dest_path=str(dest_path),
        bytes_requested=source.size,
        bytes_written=written,
        bad_sectors=bad,
        sha256=digest,
        resumed=resumed,
        cancelled=cancelled,
        checkpoint_path=str(ckpt_file) if cancelled else None,
    )


def _read_with_retries(
    source: ReadOnlySource,
    offset: int,
    size: int,
    *,
    retries: int,
    delay: float,
    sector_size: int,
    policy: str,
) -> tuple[bytes, list[BadSector]]:
    try:
        data = source.read(offset, size)
        if len(data) == size:
            return data, []
        # Short read: pad according to policy.
        if policy == "zero":
            return data + bytes(size - len(data)), [
                BadSector(
                    lba=offset // sector_size,
                    offset=offset + len(data),
                    size=size - len(data),
                    error="short read",
                    retries=0,
                )
            ]
        return data, []
    except OSError as exc:
        log.warning("read failed offset=%s size=%s err=%s", offset, size, exc)
        if size > sector_size:
            # Split into sector-sized reads to isolate the bad region.
            collected = bytearray()
            failures: list[BadSector] = []
            cursor = 0
            while cursor < size:
                piece = min(sector_size, size - cursor)
                chunk, fail = _read_with_retries(
                    source,
                    offset + cursor,
                    piece,
                    retries=retries,
                    delay=delay,
                    sector_size=sector_size,
                    policy=policy,
                )
                collected.extend(chunk)
                failures.extend(fail)
                cursor += piece
            return bytes(collected), failures
        last_exc = exc
        for attempt in range(retries):
            time.sleep(delay)
            try:
                data = source.read(offset, size)
                return data, []
            except OSError as retry_exc:
                last_exc = retry_exc
        filler = bytes(size) if policy == "zero" else b""
        return filler, [
            BadSector(
                lba=offset // sector_size,
                offset=offset,
                size=size,
                error=str(last_exc),
                retries=retries,
            )
        ]
