"""SQLite WAL / rollback-journal detection (280)."""

from __future__ import annotations

import struct

WAL_MAGIC = b"Wal\x00"
JOURNAL_MAGIC = bytes.fromhex("d9d505f920a163d7")


def inspect_sqlite_journal(data: bytes) -> dict:
    if data.startswith(WAL_MAGIC):
        version = struct.unpack_from(">I", data, 4)[0] if len(data) >= 8 else 0
        page = struct.unpack_from(">I", data, 8)[0] if len(data) >= 12 else 0
        return {
            "kind": "wal",
            "version": version,
            "page_size": page,
            "note": "SQLite write-ahead log detected. Frames are not replayed onto the source DB.",
        }
    if data.startswith(JOURNAL_MAGIC):
        return {
            "kind": "rollback-journal",
            "note": "SQLite rollback journal detected. Not applied to any database file.",
        }
    if data.startswith(b"SQLite format 3\x00"):
        return {"kind": "sqlite-db", "note": "Main SQLite database header"}
    return {"kind": None}
