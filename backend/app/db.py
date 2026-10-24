"""SQLite access (stdlib sqlite3, WAL mode, one process, one lock)."""
from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterable
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS apps (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, owner TEXT, business_unit TEXT, description TEXT, risk_tier TEXT,
  eu_ai_act_note TEXT, model TEXT, data_classes TEXT, policy_pack TEXT, allowed_roles TEXT, default_role TEXT,
  tool_policy TEXT, enabled INTEGER DEFAULT 1, created_at TEXT, key_prefix TEXT, key_hash TEXT UNIQUE, template TEXT, is_demo INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS policy_versions (
  id INTEGER PRIMARY KEY AUTOINCREMENT, pack TEXT NOT NULL, version INTEGER NOT NULL, content TEXT NOT NULL,
  created_at TEXT NOT NULL, author TEXT, note TEXT, UNIQUE(pack, version)
);
CREATE TABLE IF NOT EXISTS audit (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL, ts TEXT NOT NULL, app_id TEXT, app_name TEXT, user TEXT, role TEXT,
  channel TEXT, original_input TEXT, redacted_input TEXT, raw_output TEXT, final_output TEXT, rule_results TEXT, final_action TEXT,
  latency TEXT, pack TEXT, pack_version INTEGER, model TEXT, engine TEXT, extra TEXT, prev_hash TEXT NOT NULL, hash TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS audit_app ON audit(app_id, ts);
CREATE TABLE IF NOT EXISTS reviews (
  id TEXT PRIMARY KEY, audit_id TEXT, app_id TEXT, app_name TEXT, kind TEXT, status TEXT DEFAULT 'open', reason TEXT, rule_ids TEXT,
  created_at TEXT, decided_at TEXT, reviewer_note TEXT, payload TEXT, severity TEXT
);
CREATE TABLE IF NOT EXISTS eval_runs (id TEXT PRIMARY KEY, ts TEXT, provider TEXT, model TEXT, results TEXT);
CREATE TABLE IF NOT EXISTS demo_cache (key TEXT PRIMARY KEY, ts TEXT, data TEXT);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
"""


class Database:
    def __init__(self, path: str) -> None:
        self.path = path
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        with self.lock:
            if path != ":memory:":
                self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.executescript(SCHEMA)

    def execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        with self.lock:
            return self.conn.execute(sql, tuple(params))

    def query(self, sql: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
        with self.lock:
            return [dict(r) for r in self.conn.execute(sql, tuple(params)).fetchall()]

    def one(self, sql: str, params: Iterable[Any] = ()) -> dict[str, Any] | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None


_db: Database | None = None
_override: ContextVar[Database | None] = ContextVar("finguard_db_override", default=None)


@contextmanager
def use_db(db: Database):
    """Temporarily route get_db() to another database in this context (used by the evaluation runner)."""
    tok = _override.set(db)
    try:
        yield db
    finally:
        _override.reset(tok)


def get_db() -> Database:
    global _db
    ov = _override.get()
    if ov is not None:
        return ov
    if _db is None:
        from .config import get_settings

        _db = Database(get_settings().db_path)
    return _db


def reset_db(path: str) -> Database:
    """Point the app at a different database (used by tests and the eval runner)."""
    global _db
    _db = Database(path)
    return _db
