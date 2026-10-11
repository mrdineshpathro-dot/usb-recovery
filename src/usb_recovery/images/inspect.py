"""Image container inspector (267) and format detection."""

from __future__ import annotations

from pathlib import Path

from usb_recovery.images.aff4 import inspect_aff4, is_aff4
from usb_recovery.images.compressed import is_gzip
from usb_recovery.images.sparse import sparse_map
from usb_recovery.images.split import discover_parts
from usb_recovery.images.vhd import is_vhd, is_vhdx, parse_vhd_footer, parse_vhdx_header
from usb_recovery.util import human_size, sha256_file


def inspect_container(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {"path": str(p), "kind": "missing"}
    if p.is_dir() or len(discover_parts(p)) > 1:
        parts = discover_parts(p)
        if len(parts) > 1:
            total = sum(x.stat().st_size for x in parts)
            return {
                "kind": "split",
                "path": str(p),
                "parts": [str(x) for x in parts],
                "size": total,
                "human_size": human_size(total),
            }
    if not p.is_file():
        return {"path": str(p), "kind": "unknown"}
    size = p.stat().st_size
    base = {
        "path": str(p),
        "size": size,
        "human_size": human_size(size),
        "sha256": sha256_file(p) if size <= 64 * 1024 * 1024 else None,
    }
    if is_gzip(p):
        return {**base, "kind": "gzip"}
    if is_aff4(p):
        return {**base, **inspect_aff4(p)}
    if is_vhdx(p):
        with open(p, "rb") as handle:
            hdr = parse_vhdx_header(handle.read(256))
        return {**base, **hdr}
    if is_vhd(p):
        with open(p, "rb") as handle:
            handle.seek(-512, 2)
            meta = parse_vhd_footer(handle.read(512))
        return {**base, **meta}
    sparse = sparse_map(p)
    kind = "sparse" if sparse.get("holes") else "raw"
    return {**base, "kind": kind, "sparse": sparse}
