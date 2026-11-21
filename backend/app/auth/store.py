"""SQLite persistence for accounts, tokens, audit log, usage, quiz attempts, progress and admin-managed content.
All SQL is parameterised: user input is never concatenated into a statement."""
from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE COLLATE NOCASE, username TEXT NOT NULL UNIQUE COLLATE NOCASE,
  password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('student','administrator')), is_active INTEGER NOT NULL DEFAULT 1,
  failed_logins INTEGER NOT NULL DEFAULT 0, locked_until REAL, created_at REAL NOT NULL, last_login_at REAL);
CREATE TABLE IF NOT EXISTS refresh_tokens(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL UNIQUE, expires_at REAL NOT NULL, revoked_at REAL, created_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS ix_refresh_user ON refresh_tokens(user_id);
CREATE TABLE IF NOT EXISTS audit_logs(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, actor_id TEXT, actor_name TEXT, action TEXT NOT NULL,
  target TEXT, detail TEXT, ip TEXT);
CREATE INDEX IF NOT EXISTS ix_audit_ts ON audit_logs(ts);
CREATE TABLE IF NOT EXISTS usage_events(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  module TEXT NOT NULL, action TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_usage_ts ON usage_events(ts);
CREATE TABLE IF NOT EXISTS quiz_attempts(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  module TEXT NOT NULL, level TEXT NOT NULL, score INTEGER NOT NULL, total INTEGER NOT NULL, percent REAL NOT NULL, by_level TEXT);
CREATE INDEX IF NOT EXISTS ix_quiz_user ON quiz_attempts(user_id);
CREATE TABLE IF NOT EXISTS progress(
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, topic_id TEXT NOT NULL, completed_at REAL NOT NULL,
  PRIMARY KEY(user_id, topic_id));
CREATE TABLE IF NOT EXISTS custom_topics(
  id INTEGER PRIMARY KEY AUTOINCREMENT, module TEXT NOT NULL, level TEXT NOT NULL, title TEXT NOT NULL, summary TEXT NOT NULL,
  points TEXT NOT NULL, example TEXT NOT NULL, exercise TEXT NOT NULL, answer TEXT NOT NULL, published INTEGER NOT NULL DEFAULT 1,
  created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS custom_questions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, module TEXT NOT NULL, level TEXT NOT NULL, prompt TEXT NOT NULL, options TEXT NOT NULL,
  correct_index INTEGER NOT NULL, explanation TEXT NOT NULL, published INTEGER NOT NULL DEFAULT 1, created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS hidden_items(kind TEXT NOT NULL, ref TEXT NOT NULL, PRIMARY KEY(kind, ref));
"""


class Store:
    def __init__(self, path: str = ":memory:"):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        with self.lock:
            self.db.execute("PRAGMA foreign_keys=ON")
            self.db.executescript(SCHEMA)
            self.db.commit()

    def run(self, sql: str, params: tuple = ()) -> int:
        with self.lock:
            cur = self.db.execute(sql, params)
            self.db.commit()
            return cur.lastrowid

    def batch(self, statements: list[tuple[str, tuple]]) -> None:
        """Run several statements atomically (all or nothing)."""
        with self.lock:
            try:
                for sql, params in statements:
                    self.db.execute(sql, params)
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise

    def all(self, sql: str, params: tuple = ()) -> list[dict]:
        with self.lock:
            return [dict(r) for r in self.db.execute(sql, params).fetchall()]

    def one(self, sql: str, params: tuple = ()) -> dict | None:
        rows = self.all(sql, params)
        return rows[0] if rows else None

    def scalar(self, sql: str, params: tuple = (), default=0):
        r = self.one(sql, params)
        if not r:
            return default
        v = next(iter(r.values()))
        return default if v is None else v


_STORE: Store | None = None
DATA_DIR = Path(os.getenv("OSLAB_DATA_DIR", Path(__file__).resolve().parents[2] / "data"))


def get_store() -> Store:
    global _STORE
    if _STORE is None:
        _STORE = Store(os.getenv("OSLAB_DB_PATH", str(DATA_DIR / "oslab.db")))
    return _STORE


def set_store(s: Store | None) -> None:
    global _STORE
    _STORE = s
