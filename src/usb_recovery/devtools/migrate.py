"""SQLite schema migrations (305)."""

from __future__ import annotations

from usb_recovery.db.store import SCHEMA, SessionStore
from usb_recovery.util import isoformat
from usb_recovery.workspace.history import TAG_SCHEMA

CURRENT_SCHEMA = 2

MIGRATIONS: dict[int, str] = {
    2: TAG_SCHEMA,
}


def current_version(store: SessionStore) -> int:
    store.conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    row = store.conn.execute("SELECT MAX(version) AS v FROM schema_migrations").fetchone()
    return int(row["v"] or 0) if row and row["v"] is not None else 0


def migrate(store: SessionStore, target: int = CURRENT_SCHEMA) -> list[int]:
    applied: list[int] = []
    # Ensure base schema exists.
    store.conn.executescript(SCHEMA)
    ver = current_version(store)
    if ver == 0:
        store.conn.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (1, ?)",
            (isoformat(),),
        )
        store.conn.commit()
        ver = 1
        applied.append(1)
    for version in range(ver + 1, target + 1):
        sql = MIGRATIONS.get(version)
        if sql:
            store.conn.executescript(sql)
        store.conn.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (version, isoformat()),
        )
        store.conn.commit()
        applied.append(version)
    return applied
