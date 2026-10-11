"""Signature-based file carving with header/footer bounds and validators."""

from __future__ import annotations

import threading
from typing import Iterable

from usb_recovery.carving.signatures import FileSignature, filter_signatures, load_signatures
from usb_recovery.carving.validators import run_validator
from usb_recovery.devices.base import ReadOnlySource
from usb_recovery.exceptions import CancelledError
from usb_recovery.logging_config import get_logger
from usb_recovery.models import Candidate, ProgressCallback, ProgressEvent, ScanOptions
from usb_recovery.util import iter_overlapping_windows, new_id, sha256_bytes

log = get_logger("carver")


def _refine_zip_type(data: bytes, sig: FileSignature) -> tuple[str, str, str]:
    sample = data[: min(len(data), 2_000_000)]
    if b"word/" in sample and b"[Content_Types].xml" in sample:
        return "document.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"
    if b"xl/" in sample and b"[Content_Types].xml" in sample:
        return "spreadsheet.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"
    if b"ppt/" in sample and b"[Content_Types].xml" in sample:
        return "presentation.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation", "pptx"
    return "carved.zip", sig.mime, "zip"


def _candidate_from_hit(
    sig: FileSignature,
    offset: int,
    blob: bytes,
    *,
    footer_found: bool,
) -> Candidate:
    ok, notes = run_validator(sig.validator, blob)
    name = f"carved_{offset:08x}.{sig.extensions[0] if sig.extensions else 'bin'}"
    mime = sig.mime
    ext = sig.extensions[0] if sig.extensions else "bin"
    if sig.id == "zip":
        name, mime, ext = _refine_zip_type(blob, sig)
        name = f"carved_{offset:08x}.{ext}"
    if sig.id == "webp" and (len(blob) < 12 or blob[8:12] != b"WEBP"):
        # RIFF header is shared; skip non-webp in webp handler — caller still
        # creates WAV/AVI via their own signatures.
        pass
    reasons = [f"header match for {sig.name}"]
    if footer_found and sig.footer:
        reasons.append("matching footer located")
    elif sig.footer:
        reasons.append("footer not found; bounded by max carve size")
    if ok is True:
        reasons.append("structure validator passed: " + "; ".join(notes))
        confidence = 72.0 if footer_found else 58.0
    elif ok is False:
        reasons.append("structure validator failed: " + "; ".join(notes))
        confidence = 28.0
    else:
        confidence = 50.0 if footer_found else 36.0
    status = "carved" if ok is not False else "partial"
    return Candidate(
        id=new_id("carve-"),
        name=name,
        size=len(blob),
        file_type=ext,
        mime=mime,
        method="carved",
        status=status,  # type: ignore[arg-type]
        source_offset=offset,
        confidence=confidence,
        confidence_reasons=reasons,
        extension=ext,
        sha256=sha256_bytes(blob) if blob else None,
        notes=list(notes),
        extra={"content": blob, "signature_id": sig.id, "footer_found": footer_found},
    )


def _skip_riff_mismatch(sig: FileSignature, blob: bytes) -> bool:
    if sig.id == "webp":
        return not (len(blob) >= 12 and blob[8:12] == b"WEBP")
    if sig.id == "wav":
        return not (len(blob) >= 12 and blob[8:12] == b"WAVE")
    if sig.id == "avi":
        return not (len(blob) >= 12 and blob[8:12] == b"AVI ")
    return False


def carve_region(
    source: ReadOnlySource,
    start: int,
    length: int,
    signatures: Iterable[FileSignature],
    *,
    options: ScanOptions,
    progress: ProgressCallback | None = None,
    cancel: threading.Event | None = None,
    phase: str = "carve",
) -> list[Candidate]:
    sigs = list(signatures)
    if not sigs or length <= 0:
        return []
    overlap = max(len(s.header) + s.header_offset for s in sigs) + 8
    found: list[Candidate] = []
    seen_offsets: set[tuple[str, int]] = set()
    done = 0
    for win_off, win_size in iter_overlapping_windows(length, options.carve_window, overlap):
        if cancel is not None and cancel.is_set():
            raise CancelledError("carve cancelled")
        absolute = start + win_off
        window = source.read(absolute, win_size)
        if not window:
            break
        for sig in sigs:
            needle = sig.header
            begin = 0
            while True:
                idx = window.find(needle, begin)
                if idx < 0:
                    break
                header_abs = absolute + idx - sig.header_offset
                if header_abs < start:
                    begin = idx + 1
                    continue
                key = (sig.id, header_abs)
                if key in seen_offsets:
                    begin = idx + 1
                    continue
                seen_offsets.add(key)
                max_size = min(sig.max_size, options.max_carve_size, start + length - header_abs)
                blob = source.read(header_abs, max_size)
                footer_found = False
                if sig.footer:
                    # Search footer after the header bytes.
                    rel = blob.find(sig.footer, len(sig.header) + sig.header_offset)
                    if rel >= 0:
                        blob = blob[: rel + len(sig.footer)]
                        footer_found = True
                elif sig.id in {"webp", "wav", "avi"} and len(blob) >= 8:
                    riff_size = int.from_bytes(blob[4:8], "little") + 8
                    if 12 < riff_size <= len(blob):
                        blob = blob[:riff_size]
                        footer_found = True
                elif sig.id == "bmp" and len(blob) >= 6:
                    size = int.from_bytes(blob[2:6], "little")
                    if 14 < size <= len(blob):
                        blob = blob[:size]
                        footer_found = True
                elif sig.id == "mp4" and len(blob) >= 4:
                    box = int.from_bytes(blob[0:4], "big")
                    # Keep a reasonable slice; ftyp size is not the file size.
                    blob = blob[: min(len(blob), max(box, 256 * 1024), max_size)]
                if _skip_riff_mismatch(sig, blob):
                    begin = idx + 1
                    continue
                found.append(_candidate_from_hit(sig, header_abs, blob, footer_found=footer_found))
                begin = idx + 1
        done += win_size
        if progress:
            progress(
                ProgressEvent(
                    phase=phase,
                    current=min(done, length),
                    total=length,
                    message=f"Carving {phase}",
                    bytes_done=min(done, length),
                    bytes_total=length,
                )
            )
    return found


def carve_source(
    source: ReadOnlySource,
    options: ScanOptions,
    *,
    regions: list[tuple[int, int]] | None = None,
    progress: ProgressCallback | None = None,
    cancel: threading.Event | None = None,
    signature_ids: list[str] | None = None,
) -> list[Candidate]:
    _, sigs = load_signatures()
    sigs = filter_signatures(sigs, signature_ids or options.signatures)
    if regions is None:
        regions = [(0, source.size)]
    all_hits: list[Candidate] = []
    for start, length in regions:
        all_hits.extend(
            carve_region(
                source,
                start,
                length,
                sigs,
                options=options,
                progress=progress,
                cancel=cancel,
            )
        )
    return all_hits
