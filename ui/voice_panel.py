"""The voice-selection and delivery controls used by the Text-to-Speech page."""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from studio.config import (
    CHUNK_RANGE,
    MP3_BITRATES,
    OUTPUT_FORMATS,
    PAUSE_RANGE,
    PITCH_RANGE,
    SPEED_RANGE,
    VOLUME_RANGE,
)
from studio.engines.registry import get_cloning_engine, get_tts_engine
from studio.services import voice_catalog as catalog
from studio.services.health import mp3_available
from studio.services.language import detect_language
from studio.storage import repository as repo

from . import state
from .components import badge, badges, banner, html, panel
from .icons import icon


@dataclass
class VoiceSelection:
    mode: str  # "standard" | "custom"
    voice_id: str | None = None
    profile_id: int | None = None
    language: str | None = None
    speaker_id: int | None = None
    label: str = ""
    ready: bool = False
    problem: str = ""  # shown to the user when ``ready`` is False


def _default_language(voices) -> str | None:
    codes = [code for code, _ in catalog.language_options(voices)]
    if not codes:
        return None
    family = detect_language(st.session_state.get("p_tts_text", ""))
    if family:
        for code in codes:
            if code.replace("-", "_").split("_")[0].lower() == family:
                return code
    for preferred in ("en_US", "en_GB"):
        if preferred in codes:
            return preferred
    return codes[0]


def _setup_banner(status) -> None:
    banner("warning", status.message, "Standard voices need an offline engine with at least one voice: Piper (see README) and/or Meta MMS for Urdu, Hindi, Arabic and more.", list(status.hints))


def _standard() -> VoiceSelection:
    engine = get_tts_engine()
    status = engine.status()
    voices = catalog.standard_voices()
    if not status.available or not voices:
        _setup_banner(status)
        return VoiceSelection("standard", problem=status.message)

    ss = st.session_state
    languages = catalog.language_options(voices)
    codes = [c for c, _ in languages]
    names = dict(languages)
    if ss.get("p_tts_lang") not in codes:
        ss["p_tts_lang"] = _default_language(voices)
    st.selectbox("Language", codes, key="p_tts_lang", format_func=lambda c: names.get(c, c))

    in_language = catalog.filter_voices(voices, ss["p_tts_lang"], None)
    if catalog.has_gender_info(in_language):
        genders = ["any", "female", "male"]
        state.select_valid("p_tts_gender", genders, "any")
        st.selectbox(
            "Gender",
            genders,
            key="p_tts_gender",
            format_func=lambda g: {"any": "Any", "female": "Female", "male": "Male"}[g],
        )
        candidates = catalog.filter_voices(voices, ss["p_tts_lang"], ss["p_tts_gender"])
    else:
        candidates = in_language
        st.caption("Gender is not listed for these voice models.")
    if not candidates:
        banner("info", "No voice matches", "Try a different gender or language.")
        return VoiceSelection("standard", language=ss["p_tts_lang"], problem="No voice matches the filters.")

    by_id = {v.id: v for v in candidates}
    state.select_valid("p_tts_voice", list(by_id))
    st.selectbox("Voice", list(by_id), key="p_tts_voice", format_func=lambda i: catalog.voice_label(by_id[i]))
    voice = by_id[ss["p_tts_voice"]]

    speaker_id = None
    if voice.is_multispeaker:
        speakers = dict(voice.speakers)
        state.select_valid("p_tts_speaker", list(speakers))
        st.selectbox("Speaker", list(speakers), key="p_tts_speaker", format_func=lambda i: speakers[i])
        speaker_id = int(ss["p_tts_speaker"])

    tags = [badge(voice.quality.replace("_", " ").title(), "accent"), badge(f"{voice.sample_rate // 1000} kHz", "neutral")]
    if voice.gender in ("female", "male"):
        tags.append(badge(voice.gender.title(), "info"))
    html(badges(tags))
    return VoiceSelection(
        "standard",
        voice_id=voice.id,
        language=voice.language_code,
        speaker_id=speaker_id,
        label=f"{voice.name} · {voice.language_code}",
        ready=True,
    )


def _custom() -> VoiceSelection:
    profiles = repo.list_voice_profiles()
    if not profiles:
        banner("info", "No custom voices yet", "Record or upload a reference in Custom Voice to create one.")
        st.button("Create a custom voice", key="tts_goto_voice", on_click=state.go, args=("voice",), icon=":material/mic:")
        return VoiceSelection("custom", problem="No custom voice profiles exist yet.")

    by_id = {p["id"]: p for p in profiles}
    state.select_valid("p_tts_profile", list(by_id))
    st.selectbox(
        "Custom voice",
        list(by_id),
        key="p_tts_profile",
        format_func=lambda i: f"{by_id[i]['name']}  ·  {'ready' if by_id[i]['model_ready'] else 'reference only'}",
    )
    profile = by_id[st.session_state["p_tts_profile"]]
    engine = get_cloning_engine(profile.get("engine_id"))
    engine_status = engine.status()

    if not engine_status.available:
        banner(
            "warning",
            "Voice cloning is not available",
            "No offline cloning engine is installed, so this voice cannot speak yet. Your reference is saved safely.",
            list(engine_status.hints),
        )
        problem = "No cloning engine is installed."
    elif not profile.get("model_ready"):
        banner("warning", "Speaker model not built", "Open Custom Voice > My voices and build a model for this profile.")
        problem = "This profile has no speaker model yet."
    else:
        problem = ""
    tags = [badge(f"{profile['quality_level'].title()} reference", "accent"), badge("Ready" if not problem else "Reference only", "success" if not problem else "warning")]
    html(badges(tags))
    return VoiceSelection(
        "custom",
        profile_id=int(profile["id"]),
        language=profile.get("language"),
        label=f"{profile['name']} (custom)",
        ready=not problem,
        problem=problem,
    )


def render_voice_panel() -> VoiceSelection:
    """Draw the voice and delivery controls and return the current selection."""
    ss = st.session_state
    with panel("tts-voice"):
        html(f'<div class="vs-section" style="margin-top:0">{icon("mic")}<h2>Voice</h2></div>')
        st.radio(
            "Voice mode",
            ["standard", "custom"],
            key="seg_tts_mode",
            horizontal=True,
            format_func=lambda m: "Standard voice" if m == "standard" else "Custom voice",
            label_visibility="collapsed",
        )
        selection = _standard() if ss["seg_tts_mode"] == "standard" else _custom()

        html(f'<div class="vs-section" style="margin:1.2rem 0 .5rem">{icon("settings")}<h2>Delivery</h2></div>')
        st.slider("Speed", *SPEED_RANGE, step=0.05, key="p_tts_speed", format="%.2fx", help="1.00x is the voice's natural pace.")
        st.slider(
            "Pitch",
            *PITCH_RANGE,
            step=0.5,
            key="p_tts_pitch",
            format="%+.1f st",
            help="Semitones. Applied after synthesis, so large values may sound processed.",
        )
        st.slider("Volume", *VOLUME_RANGE, step=1.0, key="p_tts_volume", format="%+.0f dB", help="Gain applied to the final audio.")

        with st.expander("Advanced and output"):
            st.slider("Pause between parts (ms)", *PAUSE_RANGE, step=25, key="p_tts_pause")
            st.slider("Maximum characters per part", *CHUNK_RANGE, step=50, key="p_tts_chunk", help="Long text is split at sentence boundaries into parts of at most this size.")
            left, right = st.columns(2)
            left.toggle("Normalize loudness", key="p_tts_normalize")
            right.toggle("Trim silence", key="p_tts_trim")
            st.selectbox("Export format", list(OUTPUT_FORMATS), key="p_tts_format")
            if "MP3" in ss["p_tts_format"]:
                if mp3_available():
                    st.selectbox("MP3 bitrate (kbps)", list(MP3_BITRATES), key="p_tts_bitrate")
                else:
                    banner("warning", "MP3 encoder not installed", "Run `uv pip install lameenc` and restart. WAV will be exported meanwhile.")
    return selection
