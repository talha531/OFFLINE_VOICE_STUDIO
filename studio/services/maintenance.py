"""Disk usage and clean-up helpers for the Settings page. Everything stays inside the data folder."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from ..config import get_paths
from ..storage import repository as repo


@dataclass(frozen=True)
class StorageSummary:
    root: Path
    database: int
    audio: int
    voices: int
    temp: int
    models: int

    @property
    def total(self) -> int:
        return self.database + self.audio + self.voices + self.temp


def folder_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    total = 0
    for item in path.rglob("*"):
        try:
            if item.is_file():
                total += item.stat().st_size
        except OSError:
            continue
    return total


def storage_summary() -> StorageSummary:
    paths = get_paths()
    db_files = [paths.db, paths.db.with_name(paths.db.name + "-wal"), paths.db.with_name(paths.db.name + "-shm")]
    return StorageSummary(
        root=paths.root,
        database=sum(folder_size(p) for p in db_files),
        audio=folder_size(paths.audio),
        voices=folder_size(paths.references) + folder_size(paths.voice_models),
        temp=folder_size(paths.temp),
        models=folder_size(paths.piper_models),
    )


def clear_temp_files() -> int:
    """Delete everything in the temp folder. Returns the number of bytes freed."""
    temp = get_paths().temp
    freed = folder_size(temp)
    for item in temp.glob("*"):
        try:
            shutil.rmtree(item) if item.is_dir() else item.unlink()
        except OSError:
            continue
    return freed


def delete_all_audio() -> int:
    """Remove every generated audio file and its library entry. History is kept. Returns the count."""
    items = repo.list_audio()
    for item in items:
        repo.delete_audio(item["id"], delete_file=True)
    return len(items)
