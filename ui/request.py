"""Builds a ``GenerationRequest`` from the Text-to-Speech controls and fingerprints it."""

from __future__ import annotations

import hashlib
import json

import streamlit as st

from studio.services.health import mp3_available
from studio.services.pipeline import GenerationRequest

from .voice_panel import VoiceSelection


def export_formats(choice: str) -> tuple[str, ...]:
    formats = ("wav", "mp3") if choice == "WAV + MP3" else (choice.lower(),)
    if "mp3" in formats and not mp3_available():
        formats = tuple(f for f in formats if f != "mp3") or ("wav",)
    return formats


def build_request(selection: VoiceSelection, text: str) -> GenerationRequest:
    ss = st.session_state
    return GenerationRequest(
        text=text.strip(),
        title=str(ss.get("p_tts_title", "")).strip(),
        source=str(ss.get("tts_source", "Typed text")),
        mode=selection.mode,
        voice_id=selection.voice_id,
        profile_id=selection.profile_id,
        language=selection.language,
        speaker_id=selection.speaker_id,
        speed=float(ss["p_tts_speed"]),
        pitch=float(ss["p_tts_pitch"]),
        volume_db=float(ss["p_tts_volume"]),
        normalize=bool(ss["p_tts_normalize"]),
        trim_silence=bool(ss["p_tts_trim"]),
        pause_ms=int(ss["p_tts_pause"]),
        max_chars=int(ss["p_tts_chunk"]),
        formats=export_formats(str(ss["p_tts_format"])),
        mp3_bitrate=int(ss.get("p_tts_bitrate", 192)),
    )


def audio_signature(request: GenerationRequest) -> str:
    """Fingerprint of everything that changes how the audio *sounds* (not file format or title)."""
    payload = request.params()
    payload.pop("formats", None)
    payload["text"] = request.text
    return hashlib.sha1(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()
