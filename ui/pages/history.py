"""History: every generation run, with status, settings used, and one-click reuse."""

from __future__ import annotations

import json

import streamlit as st

from studio.storage import repository as repo

from .. import state
from ..compat import FULL
from ..components import (
    badge,
    badges,
    banner,
    card,
    confirm_action,
    empty_state,
    esc,
    flash,
    html,
    key_values,
    page_header,
    panel,
)
from ..formatting import fmt_duration, fmt_when, plural

STATUS = {
    "All": None,
    "Completed": "done",
    "Failed": "failed",
    "Cancelled": "cancelled",
    "Interrupted": "interrupted",
}
_TONE = {"done": "success", "failed": "danger", "cancelled": "neutral", "interrupted": "warning", "running": "accent"}
_LABEL = {"done": "Completed", "failed": "Failed", "cancelled": "Cancelled", "interrupted": "Interrupted", "running": "Running"}


def _reuse(history_id: int) -> None:
    entry = repo.get_history(history_id)
    if not entry:
        return
    try:
        params = json.loads(entry.get("params_json") or "{}")
    except json.JSONDecodeError:
        params = {}
    formats = [f.upper() for f in params.get("formats", ["wav"])]
    updates = {
        "p_tts_text": entry.get("text") or "",
        "p_tts_title": entry.get("title") or "",
        "tts_source": entry.get("source") or "Typed text",
        "seg_tts_mode": params.get("mode", "standard"),
        "p_tts_speed": float(params.get("speed", 1.0)),
        "p_tts_pitch": float(params.get("pitch", 0.0)),
        "p_tts_volume": float(params.get("volume_db", 0.0)),
        "p_tts_pause": int(params.get("pause_ms", 250)),
        "p_tts_chunk": int(params.get("max_chars", 450)),
        "p_tts_normalize": bool(params.get("normalize", True)),
        "p_tts_trim": bool(params.get("trim_silence", True)),
        "p_tts_format": "WAV + MP3" if len(formats) > 1 else formats[0],
        "tts_preview": None,
        "tts_approved_sig": None,
        "tts_outcome": None,
    }
    if params.get("mode") == "custom" and params.get("profile_id"):
        updates["p_tts_profile"] = params["profile_id"]
    else:
        if params.get("voice_id"):
            updates["p_tts_voice"] = params["voice_id"]
        if params.get("language"):
            updates["p_tts_lang"] = params["language"]
        updates["p_tts_gender"] = "any"
        updates["p_tts_speaker"] = int(params.get("speaker_id") or 0)
    flash("Text and settings loaded. Render a new preview to continue.")
    state.go("tts", **updates)


def _delete(history_id: int) -> None:
    repo.delete_history(history_id)
    flash("History entry deleted")


def _clear_all() -> None:
    repo.clear_history()
    flash("History cleared")


def _details(entry: dict) -> None:
    full = repo.get_history(entry["id"]) or entry
    try:
        params = json.loads(full.get("params_json") or "{}")
    except json.JSONDecodeError:
        params = {}
    if full.get("error"):
        banner("error" if full["status"] == "failed" else "info", "What happened", full["error"])
    key_values(
        [
            ("Source", full.get("source") or "-"),
            ("Mode", "Custom voice" if full.get("voice_mode") == "custom" else "Standard voice"),
            ("Speed", f"{params.get('speed', 1.0):.2f}x"),
            ("Pitch", f"{params.get('pitch', 0.0):+.1f} st"),
            ("Volume", f"{params.get('volume_db', 0.0):+.0f} dB"),
            ("Pause", f"{params.get('pause_ms', 0)} ms"),
            ("Part size", f"{params.get('max_chars', 0)} chars"),
            ("Formats", ", ".join(f.upper() for f in params.get("formats", []))),
        ]
    )
    text = full.get("text") or ""
    st.text_area("Text", value=text[:3000] + ("…" if len(text) > 3000 else ""), height=140, disabled=True, key=f"hist_text_{entry['id']}", label_visibility="collapsed")


def render() -> None:
    ss = st.session_state
    page_header("History", "Every generation run, including failures and cancellations, kept locally.", eyebrow="Library", icon_name="history")

    with panel("hist-filters"):
        c1, c2 = st.columns([1, 2.4])
        c1.selectbox("Status", list(STATUS), key="p_hist_status", label_visibility="collapsed")
        c2.text_input("Search history", key="p_hist_search", placeholder="Search titles or voices…", label_visibility="collapsed")

    entries = repo.list_history(status=STATUS[ss["p_hist_status"]], search=ss["p_hist_search"])
    if not entries:
        filtered = ss["p_hist_status"] != "All" or ss["p_hist_search"].strip()
        empty_state(
            "history",
            "No matching runs" if filtered else "No history yet",
            "Try different filters." if filtered else "Each time you generate audio, the run is recorded here with the settings you used.",
        )
        if not filtered:
            st.button("Open Text-to-Speech", key="hist_cta", on_click=state.go, args=("tts",), type="primary", icon=":material/graphic_eq:")
        return

    left, right = st.columns([3, 1.2])
    left.caption(f"{plural(len(entries), 'run')} shown")
    with right:
        confirm_action("Clear all history", "hist_clear", "Delete every history entry? Generated audio files in your library are not affected.", _clear_all, confirm_label="Yes, clear it")

    for entry in entries:
        status = entry["status"]
        with card(f"hist-{entry['id']}"):
            main, actions = st.columns([3.2, 1.5])
            with main:
                html(
                    f'<div class="vs-title">{esc(entry["title"])}</div>'
                    + badges(
                        [
                            badge(_LABEL.get(status, status.title()), _TONE.get(status, "neutral")),
                            badge(entry["voice_label"] or "Voice not chosen", "info"),
                            badge(f"{entry['char_count'] or 0:,} chars"),
                            badge(plural(entry["chunk_count"] or 0, "part")),
                            badge(fmt_duration(entry["duration"]) if entry["duration"] else "-"),
                            badge(fmt_when(entry["created_at"])),
                        ]
                    )
                )
            with actions:
                st.button("Reuse text & settings", key=f"hist_reuse_{entry['id']}", on_click=_reuse, args=(entry["id"],), **FULL, icon=":material/replay:")
                if status == "done" and repo.audio_for_history(entry["id"]):
                    st.button("Open in Library", key=f"hist_lib_{entry['id']}", on_click=state.go, args=("library",), kwargs={"p_lib_search": entry["title"], "lib_page": 0}, **FULL, icon=":material/library_music:")
            with st.expander("Details"):
                _details(entry)
                confirm_action("Delete this entry", f"hist_del_{entry['id']}", "Delete this history entry? Audio files stay in your library.", lambda i=entry["id"]: _delete(i))
