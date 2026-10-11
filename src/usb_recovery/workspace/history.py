"""Searchable recovery history and session tags (287, 288)."""

from __future__ import annotations

import json
from typing import Any

from usb_recovery.db.store import SessionStore
from usb_recovery.util import isoformat

TAG_SCHEMA = """
CREATE TABLE IF NOT EXISTS session_tags (
    session_id TEXT NOT NULL,
    tag TEXT NOT NULL,
    created_at TEXT,
    PRIMARY KEY (session_id, tag)
);
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
"""


class HistoryStore:
    def __init__(self, store: SessionStore) -> None:
        self.store = store
        self.store.conn.executescript(TAG_SCHEMA)
        self.store.conn.commit()

    def tag(self, session_id: str, *tags: str) -> None:
        for tag in tags:
            self.store.conn.execute(
                "INSERT OR IGNORE INTO session_tags(session_id, tag, created_at) VALUES (?,?,?)",
                (session_id, tag.strip().lower(), isoformat()),
            )
        self.store.conn.commit()

    def tags_for(self, session_id: str) -> list[str]:
        rows = self.store.conn.execute(
            "SELECT tag FROM session_tags WHERE session_id=? ORDER BY tag", (session_id,)
        ).fetchall()
        return [r["tag"] for r in rows]

    def search(self, query: str) -> list[dict[str, Any]]:
        q = f"%{query.lower()}%"
        rows = self.store.conn.execute(
            "SELECT s.*, GROUP_CONCAT(t.tag) AS tags "
            "FROM sessions s LEFT JOIN session_tags t ON t.session_id = s.id "
            "WHERE lower(s.source_path) LIKE ? OR lower(s.id) LIKE ? "
            "OR lower(ifnull(s.notes,'')) LIKE ? OR lower(ifnull(t.tag,'')) LIKE ? "
            "GROUP BY s.id ORDER BY s.created_at DESC",
            (q, q, q, q),
        ).fetchall()
        return [dict(r) for r in rows]
