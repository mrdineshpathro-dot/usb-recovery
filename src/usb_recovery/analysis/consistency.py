"""Re-read selected regions and compare (272)."""

from __future__ import annotations

from usb_recovery.devices.base import ReadOnlySource
from usb_recovery.util import sha256_bytes


def verify_read_consistency(
    source: ReadOnlySource,
    offset: int,
    size: int,
    *,
    passes: int = 2,
) -> dict:
    size = min(size, max(0, source.size - offset))
    digests: list[str] = []
    first: bytes | None = None
    for _ in range(max(1, passes)):
        data = source.read(offset, size)
        digests.append(sha256_bytes(data))
        if first is None:
            first = data
    consistent = len(set(digests)) == 1
    return {
        "offset": offset,
        "size": size,
        "passes": passes,
        "digests": digests,
        "consistent": consistent,
        "note": (
            "Consistent reads do not prove the media is healthy; inconsistent reads "
            "do indicate an unstable device."
        ),
    }
