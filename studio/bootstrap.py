"""One-time process start-up: folders, database, logging, stale temp cleanup."""

from __future__ import annotations

import logging
import threading
import time
from logging.handlers import RotatingFileHandler

from .config import get_paths
from .storage.db import ensure_ready

_lock = threading.Lock()
_done = False


def bootstrap() -> None:
    global _done
    with _lock:
        if _done:
            return
        paths = get_paths()
        root = logging.getLogger()
        if not any(isinstance(h, RotatingFileHandler) for h in root.handlers):
            handler = RotatingFileHandler(paths.logs / "app.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
            root.addHandler(handler)
            root.setLevel(logging.INFO)
        ensure_ready()
        cutoff = time.time() - 24 * 3600
        for item in paths.temp.glob("*"):
            try:
                if item.is_file() and item.stat().st_mtime < cutoff:
                    item.unlink()
            except OSError:
                pass
        _done = True
