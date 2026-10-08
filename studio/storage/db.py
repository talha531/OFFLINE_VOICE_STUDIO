"""SQLite connection handling and schema. One short-lived connection per operation so that
Streamlit's script thread and background job threads can both write safely (WAL mode)."""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator

from ..config import get_paths

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    text TEXT NOT NULL,
    char_count INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS voice_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    language TEXT,
    reference_path TEXT NOT NULL,
    duration REAL,
    quality_score INTEGER,
    quality_level TEXT,
    analysis_json TEXT,
    engine_id TEXT,
    model_path TEXT,
    model_ready INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    finished_at TEXT,
    title TEXT NOT NULL,
    source TEXT,
    text TEXT,
    voice_mode TEXT,
    voice_label TEXT,
    voice_id TEXT,
    profile_id INTEGER,
    language TEXT,
    params_json TEXT,
    char_count INTEGER,
    chunk_count INTEGER,
    duration REAL,
    status TEXT NOT NULL,
    error TEXT
);
CREATE INDEX IF NOT EXISTS idx_history_created ON history(created_at DESC);

CREATE TABLE IF NOT EXISTS audio_library (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    path TEXT NOT NULL UNIQUE,
    format TEXT NOT NULL,
    duration REAL,
    size_bytes INTEGER,
    voice_label TEXT,
    language TEXT,
    text_preview TEXT,
    favorite INTEGER NOT NULL DEFAULT 0,
    history_id INTEGER,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_library_created ON audio_library(created_at DESC);
"""

_init_lock = threading.Lock()
_initialised_for: str | None = None


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(get_paths().db, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_ready() -> None:
    """Create tables once per database path and mark interrupted jobs from a previous run."""
    global _initialised_for
    db_path = str(get_paths().db)
    with _init_lock:
        if _initialised_for == db_path:
            return
        conn = _connect()
        try:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript(SCHEMA)
            conn.execute(
                "UPDATE history SET status = 'interrupted', finished_at = ?, "
                "error = 'The app was closed before this job finished.' "
                "WHERE status IN ('running', 'queued')",
                (now_iso(),),
            )
            conn.commit()
        finally:
            conn.close()
        _initialised_for = db_path


@contextmanager
def session() -> Iterator[sqlite3.Connection]:
    ensure_ready()
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
