"""SQLite-backed sessions, candidates, checkpoints, and audit events."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from usb_recovery.models import Candidate, DeviceInfo, PartitionInfo, RecoveryResult
from usb_recovery.util import isoformat, new_id

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    source_path TEXT NOT NULL,
    source_size INTEGER,
    source_sha256 TEXT,
    profile TEXT,
    status TEXT,
    notes TEXT
);
CREATE TABLE IF NOT EXISTS devices_snapshot (
    session_id TEXT PRIMARY KEY,
    json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS partitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    idx INTEGER,
    start_lba INTEGER,
    sector_count INTEGER,
    scheme TEXT,
    type_name TEXT,
    filesystem TEXT,
    json TEXT
);
CREATE TABLE IF NOT EXISTS candidates (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    name TEXT,
    original_path TEXT,
    size INTEGER,
    file_type TEXT,
    mime TEXT,
    method TEXT,
    confidence REAL,
    confidence_json TEXT,
    status TEXT,
    source_offset INTEGER,
    cluster_start INTEGER,
    extra_json TEXT,
    sha256 TEXT
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    ts TEXT NOT NULL,
    level TEXT,
    category TEXT,
    message TEXT
);
CREATE TABLE IF NOT EXISTS recovery_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    candidate_id TEXT,
    dest_path TEXT,
    status TEXT,
    recovered_sha256 TEXT,
    recovered_size INTEGER,
    error TEXT
);
CREATE TABLE IF NOT EXISTS checkpoints (
    session_id TEXT,
    kind TEXT,
    offset INTEGER,
    extra_json TEXT
);
CREATE TABLE IF NOT EXISTS config_kv (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE INDEX IF NOT EXISTS idx_candidates_session ON candidates(session_id);
CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
"""


class SessionStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else Path(":memory:")
        uri = str(self.path)
        self._mem = uri == ":memory:"
        self.conn = sqlite3.connect(uri if not self._mem else ":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()
        try:
            from usb_recovery.devtools.migrate import migrate

            migrate(self)
        except Exception:
            pass

    def close(self) -> None:
        self.conn.close()

    def create_session(self, source_path: str, source_size: int, profile: str) -> str:
        sid = new_id("sess-")
        now = isoformat()
        self.conn.execute(
            "INSERT INTO sessions(id, created_at, updated_at, source_path, source_size, profile, status) "
            "VALUES (?,?,?,?,?,?,?)",
            (sid, now, now, source_path, source_size, profile, "created"),
        )
        self.conn.commit()
        return sid

    def set_status(self, session_id: str, status: str) -> None:
        self.conn.execute(
            "UPDATE sessions SET status=?, updated_at=? WHERE id=?",
            (status, isoformat(), session_id),
        )
        self.conn.commit()

    def save_device(self, session_id: str, info: DeviceInfo) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO devices_snapshot(session_id, json) VALUES (?,?)",
            (session_id, json.dumps(info.to_dict())),
        )
        self.conn.commit()

    def save_partitions(self, session_id: str, parts: Iterable[PartitionInfo]) -> None:
        self.conn.execute("DELETE FROM partitions WHERE session_id=?", (session_id,))
        for part in parts:
            self.conn.execute(
                "INSERT INTO partitions(session_id, idx, start_lba, sector_count, scheme, type_name, filesystem, json) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    session_id,
                    part.index,
                    part.start_lba,
                    part.sector_count,
                    part.scheme,
                    part.type_name,
                    part.filesystem,
                    json.dumps(part.__dict__, default=str),
                ),
            )
        self.conn.commit()

    def add_candidates(self, session_id: str, items: Iterable[Candidate]) -> None:
        for item in items:
            extra = dict(item.extra)
            extra.pop("content", None)  # never persist file bytes in the session DB
            self.conn.execute(
                "INSERT OR REPLACE INTO candidates(id, session_id, name, original_path, size, file_type, mime, "
                "method, confidence, confidence_json, status, source_offset, cluster_start, extra_json, sha256) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    item.id,
                    session_id,
                    item.name,
                    item.original_path,
                    item.size,
                    item.file_type,
                    item.mime,
                    item.method,
                    item.confidence,
                    json.dumps(item.confidence_reasons),
                    item.status,
                    item.source_offset,
                    item.cluster_start,
                    json.dumps({"notes": item.notes, "extra": extra, "timestamps": item.timestamps.__dict__}),
                    item.sha256,
                ),
            )
        self.conn.commit()

    def list_candidates(self, session_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM candidates WHERE session_id=? ORDER BY confidence DESC, name",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_candidate(self, candidate_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM candidates WHERE id=?", (candidate_id,)).fetchone()
        return dict(row) if row else None

    def event(self, session_id: str | None, level: str, category: str, message: str) -> None:
        self.conn.execute(
            "INSERT INTO events(session_id, ts, level, category, message) VALUES (?,?,?,?,?)",
            (session_id, isoformat(), level, category, message),
        )
        self.conn.commit()

    def list_events(self, session_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM events WHERE session_id=? ORDER BY id", (session_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def record_recovery(self, session_id: str, result: RecoveryResult) -> None:
        self.conn.execute(
            "INSERT INTO recovery_queue(session_id, candidate_id, dest_path, status, recovered_sha256, recovered_size, error) "
            "VALUES (?,?,?,?,?,?,?)",
            (
                session_id,
                result.candidate_id,
                result.dest_path,
                result.status,
                result.sha256,
                result.bytes_written,
                result.error,
            ),
        )
        self.conn.commit()

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
        return dict(row) if row else None

    def list_sessions(self) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM sessions ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]
