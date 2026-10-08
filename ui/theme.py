"""Injects the design system (assets/theme.css) into the page."""

from __future__ import annotations


import streamlit as st

from studio.config import PROJECT_ROOT

_CSS_PATH = PROJECT_ROOT / "assets" / "theme.css"


@st.cache_data(show_spinner=False)
def _load_css(mtime: float) -> str:  # mtime keys the cache so edits show up on the next rerun
    return _CSS_PATH.read_text(encoding="utf-8")


def inject_theme() -> None:
    try:
        css = _load_css(_CSS_PATH.stat().st_mtime)
    except OSError:
        return  # the app still works with Streamlit's own dark theme
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
