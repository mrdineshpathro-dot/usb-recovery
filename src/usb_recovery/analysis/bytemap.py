"""Map recovered file bytes to source offsets (273, 284)."""

from __future__ import annotations

from usb_recovery.models import ByteRange, Candidate
from usb_recovery.reconstruct.regions import regions_for

RAMP = " .:-=+*#%@"


def byte_range_map(candidate: Candidate) -> dict:
    regions = regions_for(candidate)
    chain = candidate.extra.get("chain") if isinstance(candidate.extra, dict) else None
    mapping: list[dict] = []
    if isinstance(chain, list) and chain:
        # FAT-style: each cluster is a contiguous run from cluster_offset
        vol = int(candidate.extra.get("volume_offset") or 0)
        cluster_size = int(candidate.extra.get("cluster_size") or 0)
        if not cluster_size and candidate.size and len(chain):
            cluster_size = max(512, (candidate.size + len(chain) - 1) // len(chain))
        cursor = 0
        for cl in chain:
            length = cluster_size or 512
            src = vol + (int(cl) - 2) * length if int(cl) >= 2 else candidate.source_offset + cursor
            mapping.append(
                {
                    "file_start": cursor,
                    "file_end": cursor + length,
                    "source_offset": src,
                    "kind": "recovered",
                }
            )
            cursor += length
    else:
        for r in regions:
            mapping.append(
                {
                    "file_start": r.start,
                    "file_end": r.end,
                    "source_offset": candidate.source_offset + r.start,
                    "kind": r.kind,
                }
            )
    return {
        "id": candidate.id,
        "name": candidate.name,
        "source_offset": candidate.source_offset,
        "ranges": mapping,
    }


def render_byte_map(candidate: Candidate, columns: int = 48) -> str:
    regions = regions_for(candidate)
    size = candidate.size or 1
    cells = ["."] * columns
    for r in regions:
        a = min(columns - 1, int(r.start / size * columns))
        b = min(columns, max(a + 1, int(r.end / size * columns)))
        ch = "#" if r.kind == "recovered" else ("?" if r.kind == "uncertain" else " ")
        for i in range(a, b):
            cells[i] = ch
    return "".join(cells)
