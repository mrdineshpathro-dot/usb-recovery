"""Read-error heatmap (feature 221)."""

from __future__ import annotations

from usb_recovery.flash.adaptive import heatmap_cells
from usb_recovery.models import BadSector

RAMP = " .:-=+*#%@"


def render_heatmap(
    bad: list[BadSector],
    total_bytes: int,
    *,
    columns: int = 64,
    rows: int = 4,
) -> dict:
    cells = heatmap_cells(bad, total_bytes, columns * rows if rows else columns)
    if not cells:
        return {"ascii": "", "cells": [], "bad": 0, "columns": columns}
    peak = max(cells) or 1
    width = columns
    lines = []
    for r in range(max(1, rows)):
        chunk = cells[r * width : (r + 1) * width]
        line = "".join(RAMP[min(len(RAMP) - 1, int(v / peak * (len(RAMP) - 1)))] for v in chunk)
        lines.append(line)
    return {
        "ascii": "\n".join(lines),
        "cells": cells,
        "bad": len(bad),
        "columns": columns,
        "rows": rows,
        "total_bytes": total_bytes,
        "legend": "darker/heavier glyphs = more read errors in that region",
    }
