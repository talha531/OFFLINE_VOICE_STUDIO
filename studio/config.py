"""Central configuration: filesystem layout, default settings and shared constants.

Nothing in this module touches the network. All data lives under ``VOICE_STUDIO_HOME``
(default: ``./data``) and voice models under ``VOICE_STUDIO_MODELS`` (default: ``./models``).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

APP_NAME = "Offline Voice Studio"
APP_VERSION = "1.0.0"
PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Paths:
    """Resolved filesystem locations used by the application."""

    root: Path
    db: Path
    audio: Path
    references: Path
    voice_models: Path
    temp: Path
    logs: Path
    piper_models: Path

    def ensure(self) -> None:
        for folder in (
            self.root,
            self.audio,
            self.references,
            self.voice_models,
            self.temp,
            self.logs,
            self.piper_models,
        ):
            folder.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_paths() -> Paths:
    """Return (and create) the application folders. Cached for the process lifetime."""
    root = Path(os.environ.get("VOICE_STUDIO_HOME", PROJECT_ROOT / "data")).expanduser().resolve()
    models = Path(os.environ.get("VOICE_STUDIO_MODELS", PROJECT_ROOT / "models")).expanduser().resolve()
    paths = Paths(
        root=root,
        db=root / "studio.db",
        audio=root / "audio",
        references=root / "voices",
        voice_models=root / "voice_models",
        temp=root / "tmp",
        logs=root / "logs",
        piper_models=models / "piper",
    )
    paths.ensure()
    return paths


# --------------------------------------------------------------------------- defaults
DEFAULT_SETTINGS: dict[str, object] = {
    "default_speed": 1.0,
    "default_pitch": 0.0,  # semitones
    "default_volume_db": 0.0,
    "chunk_max_chars": 450,
    "pause_ms": 250,
    "normalize": True,
    "trim_silence": True,
    "default_format": "WAV",  # WAV | MP3 | WAV + MP3
    "mp3_bitrate": 192,
    "preview_chars": 300,
    "confirm_over_chars": 15000,
    "library_page_size": 12,
}

OUTPUT_FORMATS = ("WAV", "MP3", "WAV + MP3")
MP3_BITRATES = (96, 128, 160, 192, 256, 320)

# Limits for the UI controls.
SPEED_RANGE = (0.5, 2.0)
PITCH_RANGE = (-6.0, 6.0)
VOLUME_RANGE = (-12.0, 12.0)
CHUNK_RANGE = (150, 1200)
PAUSE_RANGE = (0, 1500)

MAX_UPLOAD_MB = 50
SUPPORTED_DOCUMENT_TYPES = ("pdf", "docx", "txt", "md", "markdown")
SUPPORTED_AUDIO_TYPES = ("wav", "flac", "ogg", "mp3")

# Short language-family names (used for detection and custom voice profiles).
LANGUAGE_FAMILIES: dict[str, str] = {
    "en": "English",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "ru": "Russian",
    "uk": "Ukrainian",
    "pl": "Polish",
    "tr": "Turkish",
    "ar": "Arabic",
    "hi": "Hindi",
    "ur": "Urdu",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "sv": "Swedish",
    "cs": "Czech",
    "fa": "Persian",
    "pa": "Punjabi",
    "ps": "Pashto",
    "sd": "Sindhi",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu",
    "ml": "Malayalam",
    "kn": "Kannada",
    "gu": "Gujarati",
    "mr": "Marathi",
    "th": "Thai",
    "vi": "Vietnamese",
    "id": "Indonesian",
    "sw": "Swahili",
    "ha": "Hausa",
    "yo": "Yoruba",
    "el": "Greek",
    "he": "Hebrew",
    "ro": "Romanian",
    "hu": "Hungarian",
    "bg": "Bulgarian",
}

SAMPLE_SENTENCE = "Hello, this is a short sample so you can hear how this voice sounds."
