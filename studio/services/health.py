"""Read-only checks of what is installed, so the UI can say exactly what is missing and how to fix it."""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass

from ..engines.registry import get_cloning_engine, get_tts_engine


@dataclass(frozen=True)
class HealthCheck:
    id: str
    label: str
    ok: bool
    detail: str
    required: bool = True


def _has(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def mp3_available() -> bool:
    return _has("lameenc")


def run_checks() -> list[HealthCheck]:
    tts = get_tts_engine()
    piper_installed = _has("piper")
    try:
        voices = tts.list_voices()
    except Exception:
        voices = []
    mms = next((e for e in getattr(tts, "engines", []) if e.id == "mms"), None)
    mms_voices = mms.list_voices() if mms else []
    mms_deps = bool(mms) and mms.dependencies_installed()
    cloning = get_cloning_engine()
    cloning_status = cloning.status()

    return [
        HealthCheck(
            "piper",
            "Piper speech engine",
            piper_installed,
            "Installed." if piper_installed else "Not installed. Run `uv pip install piper-tts`, then restart.",
        ),
        HealthCheck(
            "voices",
            "Voice models",
            bool(voices),
            f"{len(voices)} installed." if voices else "None found. Run `python scripts/download_voices.py` once (needs internet), or copy .onnx files into models/piper.",
        ),
        HealthCheck(
            "mms",
            "Extra languages (MMS)",
            bool(mms_voices) and mms_deps,
            (
                f"{len(mms_voices)} language model(s) ready."
                if mms_voices and mms_deps
                else "Models found, but torch/transformers missing: `uv pip install -r requirements-mms.txt`."
                if mms_voices
                else "Optional. For Urdu, Hindi, Arabic and more: `python scripts/download_mms.py urd-script_arabic hin ara`."
            ),
            required=False,
        ),
        HealthCheck(
            "mp3",
            "MP3 export",
            mp3_available(),
            "Ready." if mp3_available() else "Optional. Run `uv pip install lameenc` to enable MP3 (WAV always works).",
            required=False,
        ),
        HealthCheck(
            "pdf",
            "PDF import",
            _has("pypdf"),
            "Ready." if _has("pypdf") else "Run `uv pip install pypdf`.",
            required=False,
        ),
        HealthCheck(
            "docx",
            "Word (DOCX) import",
            _has("docx"),
            "Ready." if _has("docx") else "Run `uv pip install python-docx`.",
            required=False,
        ),
        HealthCheck(
            "audio-read",
            "Reference audio formats",
            _has("soundfile"),
            "WAV, FLAC, OGG and MP3." if _has("soundfile") else "WAV only. Run `uv pip install soundfile` for FLAC, OGG and MP3.",
            required=False,
        ),
        HealthCheck(
            "cloning",
            "Voice-cloning engine",
            cloning_status.available,
            cloning_status.message if cloning_status.available else "None installed. Profiles are stored as validated references only.",
            required=False,
        ),
        HealthCheck(
            "language",
            "Language detection",
            _has("langdetect"),
            "Ready." if _has("langdetect") else "Optional. Run `uv pip install langdetect` (non-Latin scripts are detected without it).",
            required=False,
        ),
    ]


def speech_ready() -> bool:
    """True when standard-voice speech can be generated right now."""
    try:
        return get_tts_engine().status().available
    except Exception:
        return False
