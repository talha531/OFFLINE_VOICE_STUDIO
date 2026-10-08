"""Audio Library: browse, search, play, favourite, download and delete generated audio."""

from __future__ import annotations

import math
from pathlib import Path

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
    page_header,
    panel,
)
from ..formatting import fmt_duration, fmt_duration_words, fmt_size, fmt_when, plural
from ..icons import icon
from ..player import file_player

MAX_DOWNLOAD_BYTES = 25 * 1024 * 1024
SORTS = {"newest": "Newest first", "oldest": "Oldest first", "longest": "Longest first", "title": "Title A-Z"}


def _reset_page() -> None:
    st.session_state["lib_page"] = 0


def _clear_filters() -> None:
    ss = st.session_state
    ss.update(p_lib_search="", p_lib_fmt="All", p_lib_fav=False, p_lib_sort="newest", lib_page=0)


def _toggle_favorite(audio_id: int, value: bool) -> None:
    repo.set_favorite(audio_id, value)


def _play(audio_id: int) -> None:
    st.session_state["lib_playing"] = audio_id


def _stop() -> None:
    st.session_state["lib_playing"] = None


def _delete(audio_id: int) -> None:
    repo.delete_audio(audio_id, delete_file=True)
    if st.session_state.get("lib_playing") == audio_id:
        st.session_state["lib_playing"] = None
    flash("Audio deleted")


def _remove_entry(audio_id: int) -> None:
    repo.delete_audio(audio_id, delete_file=False)
    flash("Entry removed")


def _page_nav(page: int, pages: int, where: str) -> None:
    if pages <= 1:
        return
    left, mid, right = st.columns([1, 2, 1])
    left.button("Previous", key=f"lib_prev_{where}", on_click=lambda: st.session_state.__setitem__("lib_page", page - 1), disabled=page <= 0, **FULL, icon=":material/chevron_left:")
    mid.markdown(f"<div style='text-align:center;padding-top:.5rem' class='vs-muted'>Page {page + 1} of {pages}</div>", unsafe_allow_html=True)
    right.button("Next", key=f"lib_next_{where}", on_click=lambda: st.session_state.__setitem__("lib_page", page + 1), disabled=page >= pages - 1, **FULL, icon=":material/chevron_right:")


def _now_playing(item: dict) -> None:
    with panel("lib-now"):
        html(f'<div class="vs-section" style="margin-top:0">{icon("headphones")}<h2>Now playing</h2></div><div class="vs-title">{esc(item["title"])}</div>')
        if not file_player(item["path"]):
            banner("error", "File not found", "This audio file was moved or deleted from disk.")
        st.button("Close player", key="lib_close_player", on_click=_stop, type="tertiary")


def _item_card(item: dict) -> None:
    path = Path(item["path"])
    exists = path.exists()
    with card(f"audio-{item['id']}"):
        main, actions = st.columns([3.2, 1.5])
        with main:
            star = icon("star") if item["favorite"] else ""
            tags = [
                badge(item["format"].upper(), "accent"),
                badge(fmt_duration(item["duration"]), "neutral", "clock"),
                badge(fmt_size(item["size_bytes"])),
                badge(item["voice_label"] or "Unknown voice", "info"),
                badge(fmt_when(item["created_at"])),
            ]
            if not exists:
                tags.insert(0, badge("File missing", "danger", "alert"))
            html(f'<div class="vs-title" style="display:flex;gap:.4rem;align-items:center"><span style="color:var(--amber)">{star}</span>{esc(item["title"])}</div>' + badges(tags))
            if item.get("text_preview"):
                html(f'<div class="vs-text-preview">{esc(item["text_preview"])}</div>')
        with actions:
            if exists:
                st.button("Play", key=f"lib_play_{item['id']}", on_click=_play, args=(item["id"],), type="primary", **FULL, icon=":material/play_arrow:")
                row = st.columns(2)
                row[0].button("Unstar" if item["favorite"] else "Star", key=f"lib_fav_{item['id']}", on_click=_toggle_favorite, args=(item["id"], not item["favorite"]), **FULL, icon=":material/star:")
                if item["size_bytes"] and item["size_bytes"] <= MAX_DOWNLOAD_BYTES:
                    row[1].download_button("Save", data=path.read_bytes(), file_name=path.name, mime="audio/mpeg" if item["format"] == "mp3" else "audio/wav", key=f"lib_dl_{item['id']}", **FULL, icon=":material/download:")
                else:
                    row[1].button("Save", key=f"lib_dl_big_{item['id']}", disabled=True, **FULL, help=f"Large file. Copy it from: {path}")
                confirm_action("Delete", f"lib_del_{item['id']}", f"Delete “{item['title']}” ({item['format'].upper()}) and its file from disk? This cannot be undone.", lambda i=item["id"]: _delete(i))
            else:
                st.button("Remove entry", key=f"lib_rm_{item['id']}", on_click=_remove_entry, args=(item["id"],), **FULL, icon=":material/delete:")
        st.caption(str(path))


def render() -> None:
    ss = st.session_state
    page_header("Audio Library", "Everything you have generated, stored on this computer.", eyebrow="Library", icon_name="library")

    with panel("lib-filters"):
        c1, c2, c3, c4 = st.columns([2.4, 1, 1.3, 1.1])
        c1.text_input("Search", key="p_lib_search", placeholder="Search titles, voices or text…", on_change=_reset_page, label_visibility="collapsed")
        c2.selectbox("Format", ["All", "WAV", "MP3"], key="p_lib_fmt", on_change=_reset_page, label_visibility="collapsed")
        c3.selectbox("Sort", list(SORTS), key="p_lib_sort", format_func=SORTS.get, on_change=_reset_page, label_visibility="collapsed")
        c4.toggle("Favourites", key="p_lib_fav", on_change=_reset_page)

    items = repo.list_audio(
        search=ss["p_lib_search"],
        fmt=None if ss["p_lib_fmt"] == "All" else ss["p_lib_fmt"],
        favorites_only=bool(ss["p_lib_fav"]),
        sort=ss["p_lib_sort"],
    )
    filtered = bool(ss["p_lib_search"].strip() or ss["p_lib_fmt"] != "All" or ss["p_lib_fav"])

    if not items:
        if filtered:
            empty_state("library", "Nothing matches these filters", "Try another search or clear the filters.")
            st.button("Clear filters", key="lib_clear", on_click=_clear_filters)
        else:
            empty_state("library", "Your library is empty", "Generated audio appears here automatically. Create your first one in Text-to-Speech.")
            st.button("Open Text-to-Speech", key="lib_cta", on_click=state.go, args=("tts",), type="primary", icon=":material/graphic_eq:")
        return

    total_seconds = sum(i["duration"] or 0 for i in items if i["format"] == "wav") or sum(i["duration"] or 0 for i in items)
    st.caption(f"{plural(len(items), 'file')}  ·  {fmt_duration_words(total_seconds)} of audio  ·  {fmt_size(sum(i['size_bytes'] or 0 for i in items))}")

    playing = ss.get("lib_playing")
    if playing:
        current = repo.get_audio(playing)
        if current:
            _now_playing(current)
        else:
            ss["lib_playing"] = None

    page_size = max(4, int(repo.get_settings()["library_page_size"]))
    pages = max(1, math.ceil(len(items) / page_size))
    page = min(max(0, int(ss["lib_page"])), pages - 1)
    ss["lib_page"] = page
    for item in items[page * page_size : (page + 1) * page_size]:
        _item_card(item)
    _page_nav(page, pages, "bottom")
