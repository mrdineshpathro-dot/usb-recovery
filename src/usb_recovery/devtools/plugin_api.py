"""Plugin API version check (306)."""

from __future__ import annotations

import ast
from pathlib import Path

PLUGIN_API = "1.0"


def check_plugin_api(path: str | Path) -> dict:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    version = None
    for line in text.splitlines()[:40]:
        if "PLUGIN_API" in line and "=" in line:
            try:
                tree = ast.parse(line)
                assign = tree.body[0]
                if isinstance(assign, ast.Assign):
                    version = ast.literal_eval(assign.value)
            except Exception:
                rest = line.split("=", 1)[1].strip().strip("\"'")
                version = rest
            break
    ok = version == PLUGIN_API
    return {
        "path": str(path),
        "required": PLUGIN_API,
        "found": version,
        "compatible": ok,
        "note": "Plugins without PLUGIN_API are refused.",
    }
