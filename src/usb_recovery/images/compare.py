"""Compare two acquisition attempts (feature 269)."""

from __future__ import annotations

import hashlib
from pathlib import Path

from usb_recovery.util import human_size


def compare_images(
    a: str | Path,
    b: str | Path,
    *,
    block: int = 1024 * 1024,
    max_diffs: int = 64,
) -> dict:
    pa, pb = Path(a), Path(b)
    sa, sb = pa.stat().st_size, pb.stat().st_size
    diffs: list[dict] = []
    matched = 0
    with open(pa, "rb") as fa, open(pb, "rb") as fb:
        offset = 0
        while True:
            ca, cb = fa.read(block), fb.read(block)
            if not ca and not cb:
                break
            n = max(len(ca), len(cb))
            if ca == cb:
                matched += len(ca)
            else:
                # find first differing byte in this block
                lim = min(len(ca), len(cb))
                delta = next((i for i in range(lim) if ca[i] != cb[i]), lim)
                if len(diffs) < max_diffs:
                    diffs.append(
                        {
                            "offset": offset + delta,
                            "a_len": len(ca),
                            "b_len": len(cb),
                            "a_sha256": hashlib.sha256(ca).hexdigest(),
                            "b_sha256": hashlib.sha256(cb).hexdigest(),
                        }
                    )
            offset += n
    return {
        "a": str(pa),
        "b": str(pb),
        "size_a": sa,
        "size_b": sb,
        "size_mismatch": sa != sb,
        "matched_bytes": matched,
        "diff_blocks": diffs,
        "identical": sa == sb and not diffs,
        "note": f"Compared in {human_size(block)} blocks. Not a bitwise guarantee beyond the compared range.",
    }
