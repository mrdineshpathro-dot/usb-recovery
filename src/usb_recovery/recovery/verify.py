"""Verify recovered files against expected size and optional hashes."""

from __future__ import annotations

from pathlib import Path

from usb_recovery.models import RecoveryResult
from usb_recovery.util import sha256_file


def verify_recovered(
    dest: Path,
    *,
    expected_size: int | None,
    expected_sha256: str | None,
    compute_hash: bool,
) -> tuple[bool | None, str | None, int]:
    if not dest.exists():
        return False, None, 0
    size = dest.stat().st_size
    digest = sha256_file(dest) if compute_hash else None
    size_ok: bool | None = None
    if expected_size is not None:
        size_ok = size == expected_size
    if expected_sha256 and digest and expected_sha256 != digest:
        size_ok = False if size_ok is None else size_ok
    return size_ok, digest, size


def result_from_file(
    candidate_id: str,
    dest: Path,
    *,
    expected_size: int | None,
    expected_sha256: str | None,
    compute_hash: bool,
) -> RecoveryResult:
    size_ok, digest, size = verify_recovered(
        dest,
        expected_size=expected_size,
        expected_sha256=expected_sha256,
        compute_hash=compute_hash,
    )
    status: str
    if size_ok is False:
        status = "partial"
    else:
        status = "recovered"
    return RecoveryResult(
        candidate_id=candidate_id,
        dest_path=str(dest),
        status=status,  # type: ignore[arg-type]
        bytes_written=size,
        sha256=digest,
        size_match=size_ok,
    )
