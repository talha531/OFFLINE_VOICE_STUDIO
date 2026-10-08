"""Engine lookup. Cloning backends are discovered from ``studio/engines/plugins/*.py``.

A plugin module (file name not starting with ``_``) exposes ``ENGINE = MyCloningEngine``.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
import threading

from . import plugins
from .base import CloningEngine, TTSEngine
from .composite import CompositeTTSEngine
from .cloning import NullCloningEngine
from .mms_engine import MmsEngine
from .piper_engine import PiperEngine

log = logging.getLogger(__name__)

_lock = threading.Lock()
_tts: TTSEngine | None = None
_cloning: dict[str, CloningEngine] | None = None
_plugin_errors: dict[str, str] = {}


def get_tts_engine() -> TTSEngine:
    global _tts
    with _lock:
        if _tts is None:
            _tts = CompositeTTSEngine([PiperEngine(), MmsEngine()])
        return _tts


def set_tts_engine(engine: TTSEngine | None) -> None:
    """Replace the TTS engine (used by tests)."""
    global _tts
    with _lock:
        _tts = engine


def _discover() -> dict[str, CloningEngine]:
    global _cloning
    with _lock:
        if _cloning is not None:
            return _cloning
        found: dict[str, CloningEngine] = {}
        for module_info in pkgutil.iter_modules(plugins.__path__):
            if module_info.name.startswith("_"):
                continue
            try:
                module = importlib.import_module(f"{plugins.__name__}.{module_info.name}")
                engine = module.ENGINE()
                found[engine.id] = engine
            except Exception as exc:  # a broken plugin must never break the app
                log.exception("Cloning plugin %s failed to load", module_info.name)
                _plugin_errors[module_info.name] = f"{type(exc).__name__}: {exc}"
        _cloning = found
        return found


def list_cloning_engines() -> list[CloningEngine]:
    return list(_discover().values())


def plugin_load_errors() -> dict[str, str]:
    _discover()
    return dict(_plugin_errors)


def _family(language: str | None) -> str:
    return (language or "").replace("-", "_").split("_")[0].lower()


def cloning_languages() -> set[str]:
    """Language families the *available* cloning engines can speak."""
    found: set[str] = set()
    for engine in _discover().values():
        try:
            if engine.status().available:
                found.update(engine.supported_languages())
        except Exception:
            log.exception("Cloning engine %s status check failed", engine.id)
    return found


def get_cloning_engine(engine_id: str | None = None, language: str | None = None) -> CloningEngine:
    """Return the requested engine; else an available one that supports ``language``; else any
    available one; else the honest null engine."""
    engines = _discover()
    if engine_id and engine_id in engines:
        return engines[engine_id]
    available: list[CloningEngine] = []
    for engine in engines.values():
        try:
            if engine.status().available:
                available.append(engine)
        except Exception:
            log.exception("Cloning engine %s status check failed", engine.id)
    family = _family(language)
    if family:
        for engine in available:
            try:
                if family in engine.supported_languages():
                    return engine
            except Exception:
                log.exception("Cloning engine %s language check failed", engine.id)
    if available:
        return available[0]
    return NullCloningEngine()
