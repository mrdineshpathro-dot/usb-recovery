"""USB vendor/product reference (feature 227). Offline JSON, not a live lookup."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources


@lru_cache(maxsize=1)
def _table() -> dict:
    with resources.files("usb_recovery.data").joinpath("usb_ids.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)


def lookup_usb(vid: str | None, pid: str | None = None) -> dict:
    table = _table().get("vendors") or {}
    if not vid:
        return {"known": False}
    vid_n = str(vid).lower().removeprefix("0x")
    pid_n = str(pid).lower().removeprefix("0x") if pid else ""
    combo = f"{vid_n}:{pid_n}" if pid_n else ""
    if combo and combo in table:
        return {"known": True, "id": combo, **table[combo]}
    if vid_n in table:
        return {"known": True, "id": vid_n, **table[vid_n]}
    return {"known": False, "id": vid_n, "name": "unknown vendor"}
