"""SQLite WAL / rollback-journal analysis on an isolated copy (336)."""

from __future__ import annotations

import struct

from usb_recovery.analysis.wal import inspect_sqlite_journal


def analyze_sqlite_journal_copy(data: bytes) -> dict:
    """List WAL frames or rollback pages. Never applied to a live database."""
    info = inspect_sqlite_journal(data)
    kind = info.get("kind")
    if kind == "wal":
        page = int(info.get("page_size") or 0) or 4096
        frames = []
        offset = 32
        while offset + 24 + page <= len(data):
            pgno = struct.unpack_from(">I", data, offset)[0]
            db_size = struct.unpack_from(">I", data, offset + 4)[0]
            frames.append({"page": pgno, "db_pages": db_size, "offset": offset})
            offset += 24 + page
            if len(frames) > 4096:
                break
        return {
            **info,
            "frames": frames,
            "frame_count": len(frames),
            "applied": False,
            "note": "WAL frames listed on an isolated copy. They are never replayed onto a database.",
        }
    if kind == "rollback-journal":
        return {
            **info,
            "applied": False,
            "note": "Rollback journal detected. Not applied to any database file.",
        }
    if kind == "sqlite-db":
        page = struct.unpack_from(">H", data, 16)[0] if len(data) >= 18 else 0
        if page == 1:
            page = 65536
        return {**info, "page_size": page, "applied": False}
    return {**info, "applied": False}
