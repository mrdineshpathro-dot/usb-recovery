"""Saved searches, bookmarks, and workspace profiles (243, 249, 250)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from usb_recovery.db.store import SessionStore
from usb_recovery.util import isoformat, new_id

EXTRA_SCHEMA = """
CREATE TABLE IF NOT EXISTS saved_searches (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    query TEXT,
    rules_json TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS bookmarks (
    id TEXT PRIMARY KEY,
    session_id TEXT,
    candidate_id TEXT,
    offset INTEGER,
    note TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS workspace_profiles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    json TEXT NOT NULL,
    updated_at TEXT
);
"""


class WorkspaceStore:
    def __init__(self, store: SessionStore) -> None:
        self.store = store
        self.store.conn.executescript(EXTRA_SCHEMA)
        self.store.conn.commit()

    def save_search(self, name: str, query: str = "", rules: dict | None = None) -> str:
        sid = new_id("srch-")
        self.store.conn.execute(
            "INSERT INTO saved_searches(id, name, query, rules_json, created_at) VALUES (?,?,?,?,?)",
            (sid, name, query, json.dumps(rules or {}), isoformat()),
        )
        self.store.conn.commit()
        return sid

    def list_searches(self) -> list[dict[str, Any]]:
        rows = self.store.conn.execute("SELECT * FROM saved_searches ORDER BY created_at").fetchall()
        return [dict(r) for r in rows]

    def bookmark(
        self,
        *,
        session_id: str | None,
        candidate_id: str | None = None,
        offset: int | None = None,
        note: str = "",
    ) -> str:
        bid = new_id("bm-")
        self.store.conn.execute(
            "INSERT INTO bookmarks(id, session_id, candidate_id, offset, note, created_at) VALUES (?,?,?,?,?,?)",
            (bid, session_id, candidate_id, offset, note, isoformat()),
        )
        self.store.conn.commit()
        return bid

    def list_bookmarks(self, session_id: str | None = None) -> list[dict[str, Any]]:
        if session_id:
            rows = self.store.conn.execute(
                "SELECT * FROM bookmarks WHERE session_id=? ORDER BY created_at", (session_id,)
            ).fetchall()
        else:
            rows = self.store.conn.execute("SELECT * FROM bookmarks ORDER BY created_at").fetchall()
        return [dict(r) for r in rows]

    def save_profile(self, name: str, settings: dict[str, Any]) -> str:
        # Never persist passphrases or recovered paths' file contents.
        cleaned = {k: v for k, v in settings.items() if k not in {"passphrase", "vault_key"}}
        pid = new_id("ws-")
        existing = self.store.conn.execute(
            "SELECT id FROM workspace_profiles WHERE name=?", (name,)
        ).fetchone()
        if existing:
            self.store.conn.execute(
                "UPDATE workspace_profiles SET json=?, updated_at=? WHERE id=?",
                (json.dumps(cleaned), isoformat(), existing["id"]),
            )
            self.store.conn.commit()
            return existing["id"]
        self.store.conn.execute(
            "INSERT INTO workspace_profiles(id, name, json, updated_at) VALUES (?,?,?,?)",
            (pid, name, json.dumps(cleaned), isoformat()),
        )
        self.store.conn.commit()
        return pid

    def load_profile(self, name: str) -> dict[str, Any] | None:
        row = self.store.conn.execute(
            "SELECT * FROM workspace_profiles WHERE name=?", (name,)
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["settings"] = json.loads(data.pop("json"))
        return data
