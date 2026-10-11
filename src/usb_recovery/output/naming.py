"""Safe filename templates and advanced collision handling (235, 236)."""

from __future__ import annotations

from pathlib import Path

from usb_recovery.models import Candidate
from usb_recovery.util import safe_filename, unique_path


def apply_template(template: str, candidate: Candidate, *, index: int = 0) -> str:
    """Format a recovered filename. Unknown keys stay empty. Never uses path separators."""
    stem = Path(candidate.name).stem or "unnamed"
    suffix = Path(candidate.name).suffix
    values = {
        "original": safe_filename(candidate.name),
        "stem": safe_filename(stem),
        "suffix": suffix,
        "ext": candidate.extension or suffix.lstrip("."),
        "offset": f"{candidate.source_offset:08x}",
        "id": candidate.id[:12],
        "type": candidate.file_type or "bin",
        "status": candidate.status,
        "method": candidate.method,
        "index": str(index),
        "date": (candidate.timestamps.modified or candidate.timestamps.created or "nodate")[:10],
    }
    name = template
    for key, value in values.items():
        name = name.replace("{" + key + "}", str(value))
    return safe_filename(name)


def apply_folder_template(template: str, candidate: Candidate) -> Path:
    """Build a relative folder from a pattern such as `{type}/{status}`."""
    values = {
        "type": safe_filename(candidate.file_type or "bin"),
        "status": safe_filename(candidate.status),
        "method": safe_filename(candidate.method),
        "ext": safe_filename(candidate.extension or "bin"),
        "date": (candidate.timestamps.modified or candidate.timestamps.created or "nodate")[:10],
    }
    rel = template
    for key, value in values.items():
        rel = rel.replace("{" + key + "}", value)
    parts = [safe_filename(p) for p in Path(rel).parts if p not in {".", ""}]
    return Path(*parts) if parts else Path()


def resolve_collision(
    folder: Path,
    filename: str,
    *,
    strategy: str = "increment",
    digest: str | None = None,
    template: str = "{stem} ({n}){suffix}",
) -> Path:
    """
    strategy:
      increment — HELLO (1).TXT
      hash — HELLO-abcd1234.TXT
      skip — return existing path and caller should skip write
      fail — raise FileExistsError
    """
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / filename
    if not target.exists():
        return target
    if strategy == "skip":
        return target
    if strategy == "fail":
        raise FileExistsError(str(target))
    if strategy == "hash":
        token = (digest or "dup")[:8]
        stem, suffix = target.stem, target.suffix
        alt = folder / f"{stem}-{token}{suffix}"
        n = 1
        while alt.exists():
            alt = folder / f"{stem}-{token}-{n}{suffix}"
            n += 1
        return alt
    return unique_path(folder, filename, template)
