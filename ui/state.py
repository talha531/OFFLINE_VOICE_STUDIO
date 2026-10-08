"""Session state: defaults, page navigation and widget-state persistence.

Streamlit forgets the value of a keyed widget when the widget is not drawn during a run (for
example when you visit another page). Every keyed *input* widget in this app therefore uses a
key starting with ``p_`` (or ``seg_`` for segmented radios), and ``persist_widgets()`` re-writes
those values on every run so they survive page changes. Buttons and uploaders use other prefixes
and are deliberately not persisted.
"""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from studio.storage import repository as repo

PERSIST_PREFIXES = ("p_", "seg_")


@dataclass(frozen=True)
class Page:
    id: str
    label: str
    material_icon: str
    icon_name: str
    module: str


PAGES: tuple[Page, ...] = (
    Page("dashboard", "Dashboard", ":material/dashboard:", "dashboard", "dashboard"),
    Page("tts", "Text-to-Speech", ":material/graphic_eq:", "tts", "tts"),
    Page("documents", "Documents", ":material/description:", "document", "documents"),
    Page("voice", "Custom Voice", ":material/mic:", "mic", "custom_voice"),
    Page("library", "Audio Library", ":material/library_music:", "library", "library"),
    Page("history", "History", ":material/history:", "history", "history"),
    Page("settings", "Settings", ":material/settings:", "settings", "settings"),
)
PAGE_IDS = tuple(p.id for p in PAGES)


def apply_default_settings(settings: dict) -> None:
    """Copy saved defaults into the Text-to-Speech controls."""
    ss = st.session_state
    ss["p_tts_speed"] = float(settings["default_speed"])
    ss["p_tts_pitch"] = float(settings["default_pitch"])
    ss["p_tts_volume"] = float(settings["default_volume_db"])
    ss["p_tts_pause"] = int(settings["pause_ms"])
    ss["p_tts_chunk"] = int(settings["chunk_max_chars"])
    ss["p_tts_normalize"] = bool(settings["normalize"])
    ss["p_tts_trim"] = bool(settings["trim_silence"])
    ss["p_tts_format"] = str(settings["default_format"])
    ss["p_tts_bitrate"] = int(settings["mp3_bitrate"])


def init_state() -> None:
    ss = st.session_state
    if ss.get("_initialised"):
        return
    apply_default_settings(repo.get_settings())
    defaults = {
        "page": "dashboard",
        # Text-to-Speech
        "p_tts_text": "",
        "p_tts_title": "",
        "seg_tts_mode": "standard",
        "p_tts_lang": None,
        "p_tts_gender": "any",
        "p_tts_voice": None,
        "p_tts_speaker": 0,
        "p_tts_profile": None,
        "tts_source": "Typed text",
        "tts_preview": None,
        "tts_approved_sig": None,
        "tts_job_id": None,
        "tts_outcome": None,
        "tts_confirm_long": False,
        # Documents
        "seg_doc_view": "editor",
        "seg_set_view": "defaults",
        "p_doc_search": "",
        "p_doc_name": "",
        "p_doc_text": "",
        "p_doc_fix_hyphenation": True,
        "p_doc_join_lines": True,
        "p_doc_remove_page_numbers": True,
        "p_doc_strip_markdown": False,
        "p_doc_remove_urls": False,
        "doc_raw": "",
        "doc_kind": "txt",
        "doc_id": None,
        "doc_warnings": [],
        "doc_seen_upload": None,
        # Custom voice
        "seg_cv_view": "create",
        "seg_cv_method": "upload",
        "p_cv_profile": None,
        "cv_created": None,
        "cv_error": None,
        "p_cv_name": "",
        "p_cv_lang": "en",
        "p_cv_notes": "",
        "p_cv_text": "Hello, this is a short sample so you can hear how this voice sounds.",
        "cv_ref": None,
        "cv_preview": None,
        # Library / history
        "p_lib_search": "",
        "p_lib_fmt": "All",
        "p_lib_fav": False,
        "p_lib_sort": "newest",
        "lib_page": 0,
        "lib_playing": None,
        "p_hist_status": "All",
        "p_hist_search": "",
    }
    for key, value in defaults.items():
        ss.setdefault(key, value)
    ss["_initialised"] = True


def persist_widgets() -> None:
    """Keep keyed widget values alive across page switches (see module docstring)."""
    ss = st.session_state
    for key in list(ss.keys()):
        if isinstance(key, str) and key.startswith(PERSIST_PREFIXES):
            ss[key] = ss[key]


def current_page() -> str:
    page = st.session_state.get("page", "dashboard")
    return page if page in PAGE_IDS else "dashboard"


def go(page_id: str, **updates) -> None:
    """Navigate. Safe to use as a button ``on_click`` callback; ``updates`` are written to session state."""
    for key, value in updates.items():
        st.session_state[key] = value
    st.session_state["page"] = page_id if page_id in PAGE_IDS else "dashboard"


def select_valid(key: str, options: list, fallback=None) -> None:
    """Make sure the stored value of a select-like widget is one of ``options`` (before drawing it)."""
    ss = st.session_state
    if not options:
        ss[key] = fallback
    elif ss.get(key) not in options:
        ss[key] = fallback if fallback in options else options[0]
