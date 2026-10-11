"""Temporary / autosave filename patterns (276)."""

from __future__ import annotations

import re

from usb_recovery.models import Candidate

TEMP_RE = re.compile(
    r"(^~\$)|(^~)|(\.tmp$)|(\.temp$)|(\.autosave$)|(\.bak$)|(^thumbs\.db$)|"
    r"(^\.ds_store$)|(\.crdownload$)|(\.partial$)|(^etile.+)|(\.wbk$)",
    re.I,
)


def is_temp_name(name: str) -> bool:
    base = name.rsplit("/", 1)[-1]
    return bool(TEMP_RE.search(base))


def find_temp_candidates(candidates: list[Candidate]) -> list[Candidate]:
    return [c for c in candidates if is_temp_name(c.name) or is_temp_name(c.original_path or "")]
