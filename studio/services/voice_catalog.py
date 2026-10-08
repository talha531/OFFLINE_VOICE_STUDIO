"""Query helpers over the installed standard voices (language, gender, labels)."""

from __future__ import annotations

from ..engines.base import VoiceInfo
from ..engines.registry import get_tts_engine

GENDER_LABELS = {"female": "Female", "male": "Male", "unspecified": "Not specified"}


def standard_voices() -> list[VoiceInfo]:
    engine = get_tts_engine()
    try:
        return engine.list_voices()
    except Exception:
        return []


def language_options(voices: list[VoiceInfo]) -> list[tuple[str, str]]:
    """Unique (language_code, display name) pairs, sorted by name."""
    seen: dict[str, str] = {}
    for v in voices:
        seen.setdefault(v.language_code, v.language_name)
    return sorted(seen.items(), key=lambda kv: kv[1])


def has_gender_info(voices: list[VoiceInfo]) -> bool:
    return any(v.gender in ("female", "male") for v in voices)


def filter_voices(voices: list[VoiceInfo], language: str | None, gender: str | None) -> list[VoiceInfo]:
    result = voices
    if language:
        result = [v for v in result if v.language_code == language]
    if gender in ("female", "male"):
        result = [v for v in result if v.gender == gender]
    return result


def voice_label(voice: VoiceInfo) -> str:
    gender = GENDER_LABELS.get(voice.gender, "")
    parts = [voice.name, voice.quality.replace("_", " ").title()]
    if voice.gender != "unspecified":
        parts.append(gender)
    return " · ".join(parts)
