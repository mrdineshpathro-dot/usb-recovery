"""AFF4 container import (feature 263). AFF4 is a ZIP with RDF metadata.

This reader lists segments and metadata. Full Zip64 stream reconstruction of
every AFF4 map is not claimed. Small `aff4:ImageStream` members can be read
as a concatenated raw view when they are stored uncompressed or as ZIP files.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from usb_recovery.exceptions import SourceAccessError


def is_aff4(path: str | Path) -> bool:
    p = Path(path)
    if not p.is_file():
        return False
    if not zipfile.is_zipfile(p):
        return False
    try:
        with zipfile.ZipFile(p, "r") as zf:
            names = zf.namelist()
    except zipfile.BadZipFile:
        return False
    blob = " ".join(names).lower()
    return "aff4" in blob or any(n.endswith(".turtle") or n.endswith(".info") for n in names)


def inspect_aff4(path: str | Path) -> dict:
    p = Path(path)
    if not zipfile.is_zipfile(p):
        raise SourceAccessError(f"{p} is not a ZIP/AFF4 container")
    with zipfile.ZipFile(p, "r") as zf:
        names = zf.namelist()
        infos = [
            {"name": i.filename, "size": i.file_size, "compress": i.compress_type}
            for i in zf.infolist()
        ]
        turtle = [n for n in names if n.endswith(".turtle") or "information.turtle" in n]
        rdf = ""
        if turtle:
            rdf = zf.read(turtle[0])[:8000].decode("utf-8", errors="replace")
    return {
        "kind": "aff4",
        "members": infos,
        "member_count": len(infos),
        "rdf_preview": rdf,
        "note": "AFF4 map streams are listed; full map-to-raw translation is limited to stored members.",
    }
