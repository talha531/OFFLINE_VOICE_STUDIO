"""Data access for settings, documents, voice profiles, audio library and history.

All functions return plain dicts / primitives so the UI never touches SQL.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from ..config import DEFAULT_SETTINGS
from .db import now_iso, session


def _row(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


def _rows(rows: list[sqlite3.Row]) -> list[dict]:
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------- settings
def get_settings() -> dict[str, Any]:
    values = dict(DEFAULT_SETTINGS)
    with session() as db:
        for row in db.execute("SELECT key, value FROM settings"):
            if row["key"] in DEFAULT_SETTINGS:
                try:
                    values[row["key"]] = json.loads(row["value"])
                except json.JSONDecodeError:
                    pass
    return values


def save_settings(updates: dict[str, Any]) -> None:
    with session() as db:
        for key, value in updates.items():
            if key in DEFAULT_SETTINGS:
                db.execute(
                    "INSERT INTO settings(key, value) VALUES(?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (key, json.dumps(value)),
                )


def reset_settings() -> None:
    with session() as db:
        db.execute("DELETE FROM settings")


# --------------------------------------------------------------------------- documents
def add_document(name: str, kind: str, text: str) -> int:
    ts = now_iso()
    with session() as db:
        cur = db.execute(
            "INSERT INTO documents(name, kind, text, char_count, created_at, updated_at) VALUES(?,?,?,?,?,?)",
            (name, kind, text, len(text), ts, ts),
        )
        return int(cur.lastrowid)


def list_documents() -> list[dict]:
    with session() as db:
        return _rows(
            db.execute(
                "SELECT id, name, kind, char_count, created_at, updated_at FROM documents ORDER BY updated_at DESC"
            ).fetchall()
        )


def get_document(doc_id: int) -> dict | None:
    with session() as db:
        return _row(db.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone())


def update_document(doc_id: int, text: str, name: str | None = None) -> None:
    with session() as db:
        if name is not None and name.strip():
            db.execute(
                "UPDATE documents SET name = ?, text = ?, char_count = ?, updated_at = ? WHERE id = ?",
                (name.strip(), text, len(text), now_iso(), doc_id),
            )
        else:
            db.execute(
                "UPDATE documents SET text = ?, char_count = ?, updated_at = ? WHERE id = ?",
                (text, len(text), now_iso(), doc_id),
            )


def delete_document(doc_id: int) -> None:
    with session() as db:
        db.execute("DELETE FROM documents WHERE id = ?", (doc_id,))


# ----------------------------------------------------------------------- voice profiles
_PROFILE_FIELDS = {
    "name",
    "language",
    "reference_path",
    "duration",
    "quality_score",
    "quality_level",
    "analysis_json",
    "engine_id",
    "model_path",
    "model_ready",
    "notes",
}


def add_voice_profile(
    *,
    name: str,
    language: str | None,
    reference_path: str,
    duration: float,
    quality_score: int,
    quality_level: str,
    analysis: dict,
    notes: str = "",
) -> int:
    with session() as db:
        cur = db.execute(
            "INSERT INTO voice_profiles(name, language, reference_path, duration, quality_score, quality_level, "
            "analysis_json, notes, created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (name, language, reference_path, duration, quality_score, quality_level, json.dumps(analysis), notes, now_iso()),
        )
        return int(cur.lastrowid)


def list_voice_profiles() -> list[dict]:
    with session() as db:
        return _rows(db.execute("SELECT * FROM voice_profiles ORDER BY created_at DESC").fetchall())


def get_voice_profile(profile_id: int) -> dict | None:
    with session() as db:
        return _row(db.execute("SELECT * FROM voice_profiles WHERE id = ?", (profile_id,)).fetchone())


def update_voice_profile(profile_id: int, **fields: Any) -> None:
    fields = {k: v for k, v in fields.items() if k in _PROFILE_FIELDS}
    if not fields:
        return
    assignments = ", ".join(f"{k} = ?" for k in fields)
    with session() as db:
        db.execute(f"UPDATE voice_profiles SET {assignments} WHERE id = ?", (*fields.values(), profile_id))


def delete_voice_profile(profile_id: int) -> None:
    with session() as db:
        db.execute("DELETE FROM voice_profiles WHERE id = ?", (profile_id,))


# ------------------------------------------------------------------------ audio library
def add_audio(
    *,
    title: str,
    path: str,
    fmt: str,
    duration: float,
    size_bytes: int,
    voice_label: str,
    language: str | None,
    text_preview: str,
    history_id: int | None,
) -> int:
    with session() as db:
        cur = db.execute(
            "INSERT INTO audio_library(title, path, format, duration, size_bytes, voice_label, language, "
            "text_preview, history_id, created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (title, path, fmt, duration, size_bytes, voice_label, language, text_preview, history_id, now_iso()),
        )
        return int(cur.lastrowid)


def list_audio(
    *, search: str = "", fmt: str | None = None, favorites_only: bool = False, sort: str = "newest"
) -> list[dict]:
    clauses, params = [], []
    if search.strip():
        clauses.append("(title LIKE ? OR voice_label LIKE ? OR text_preview LIKE ?)")
        like = f"%{search.strip()}%"
        params += [like, like, like]
    if fmt:
        clauses.append("format = ?")
        params.append(fmt.lower())
    if favorites_only:
        clauses.append("favorite = 1")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    order = {
        "newest": "created_at DESC, id DESC",
        "oldest": "created_at ASC, id ASC",
        "longest": "duration DESC",
        "title": "title COLLATE NOCASE ASC",
    }.get(sort, "created_at DESC")
    with session() as db:
        return _rows(db.execute(f"SELECT * FROM audio_library {where} ORDER BY {order}", params).fetchall())


def get_audio(audio_id: int) -> dict | None:
    with session() as db:
        return _row(db.execute("SELECT * FROM audio_library WHERE id = ?", (audio_id,)).fetchone())


def audio_for_history(history_id: int) -> list[dict]:
    with session() as db:
        return _rows(db.execute("SELECT * FROM audio_library WHERE history_id = ?", (history_id,)).fetchall())


def set_favorite(audio_id: int, favorite: bool) -> None:
    with session() as db:
        db.execute("UPDATE audio_library SET favorite = ? WHERE id = ?", (1 if favorite else 0, audio_id))


def delete_audio(audio_id: int, *, delete_file: bool = True) -> None:
    item = get_audio(audio_id)
    with session() as db:
        db.execute("DELETE FROM audio_library WHERE id = ?", (audio_id,))
    if item and delete_file:
        try:
            Path(item["path"]).unlink(missing_ok=True)
        except OSError:
            pass


# ----------------------------------------------------------------------------- history
_HISTORY_FIELDS = {"finished_at", "duration", "chunk_count", "status", "error", "voice_label"}


def add_history(
    *,
    title: str,
    source: str,
    text: str,
    voice_mode: str,
    voice_label: str,
    voice_id: str | None,
    profile_id: int | None,
    language: str | None,
    params: dict,
    chunk_count: int,
    status: str = "running",
) -> int:
    with session() as db:
        cur = db.execute(
            "INSERT INTO history(created_at, title, source, text, voice_mode, voice_label, voice_id, profile_id, "
            "language, params_json, char_count, chunk_count, status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                now_iso(),
                title,
                source,
                text,
                voice_mode,
                voice_label,
                voice_id,
                profile_id,
                language,
                json.dumps(params),
                len(text),
                chunk_count,
                status,
            ),
        )
        return int(cur.lastrowid)


def update_history(history_id: int, **fields: Any) -> None:
    fields = {k: v for k, v in fields.items() if k in _HISTORY_FIELDS}
    if not fields:
        return
    assignments = ", ".join(f"{k} = ?" for k in fields)
    with session() as db:
        db.execute(f"UPDATE history SET {assignments} WHERE id = ?", (*fields.values(), history_id))


def list_history(*, status: str | None = None, search: str = "", limit: int = 300) -> list[dict]:
    clauses, params = [], []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if search.strip():
        clauses.append("(title LIKE ? OR voice_label LIKE ?)")
        like = f"%{search.strip()}%"
        params += [like, like]
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with session() as db:
        return _rows(
            db.execute(
                f"SELECT id, created_at, finished_at, title, source, voice_mode, voice_label, voice_id, profile_id, "
                f"language, params_json, char_count, chunk_count, duration, status, error FROM history {where} "
                f"ORDER BY created_at DESC, id DESC LIMIT ?",
                (*params, limit),
            ).fetchall()
        )


def get_history(history_id: int) -> dict | None:
    with session() as db:
        return _row(db.execute("SELECT * FROM history WHERE id = ?", (history_id,)).fetchone())


def delete_history(history_id: int) -> None:
    with session() as db:
        db.execute("DELETE FROM history WHERE id = ?", (history_id,))


def clear_history() -> None:
    with session() as db:
        db.execute("DELETE FROM history")


# ------------------------------------------------------------------------------ stats
def stats() -> dict[str, Any]:
    with session() as db:
        one = lambda sql: db.execute(sql).fetchone()[0] or 0  # noqa: E731
        return {
            "generations": one("SELECT COUNT(*) FROM history WHERE status = 'done'"),
            "failed": one("SELECT COUNT(*) FROM history WHERE status = 'failed'"),
            "audio_files": one("SELECT COUNT(*) FROM audio_library"),
            "audio_seconds": one("SELECT SUM(duration) FROM audio_library WHERE format = 'wav'")
            or one("SELECT SUM(duration) FROM audio_library"),
            "storage_bytes": one("SELECT SUM(size_bytes) FROM audio_library"),
            "voices": one("SELECT COUNT(*) FROM voice_profiles"),
            "documents": one("SELECT COUNT(*) FROM documents"),
        }
