"""Recovery exclusion rules (285)."""

from __future__ import annotations

import fnmatch
from typing import Iterable

from usb_recovery.models import Candidate


def excluded(
    candidate: Candidate,
    *,
    types: Iterable[str] | None = None,
    paths: Iterable[str] | None = None,
    ids: Iterable[str] | None = None,
) -> bool:
    if ids and candidate.id in set(ids):
        return True
    type_set = {t.lower() for t in types or []}
    if type_set and (
        candidate.file_type.lower() in type_set or candidate.extension.lower() in type_set
    ):
        return True
    path = (candidate.original_path or candidate.name or "").replace("\\", "/")
    for pattern in paths or []:
        if fnmatch.fnmatch(path.lower(), pattern.lower()) or fnmatch.fnmatch(
            candidate.name.lower(), pattern.lower()
        ):
            return True
    return False


def apply_exclusions(
    candidates: list[Candidate],
    *,
    types: Iterable[str] | None = None,
    paths: Iterable[str] | None = None,
    ids: Iterable[str] | None = None,
) -> list[Candidate]:
    return [c for c in candidates if not excluded(c, types=types, paths=paths, ids=ids)]
