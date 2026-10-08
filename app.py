"""Offline Voice Studio - entry point.  Run with:  streamlit run app.py"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from studio.bootstrap import bootstrap  # noqa: E402
from studio.config import APP_NAME  # noqa: E402
from ui import state  # noqa: E402
from ui.components import banner, show_flash  # noqa: E402
from ui.sidebar import render_sidebar  # noqa: E402
from ui.theme import inject_theme  # noqa: E402

st.set_page_config(
    page_title=APP_NAME,
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main() -> None:
    try:
        bootstrap()
    except Exception as exc:  # disk full, read-only folder, corrupt database...
        st.error(f"{APP_NAME} could not prepare its data folder: {exc}")
        st.info("Set the VOICE_STUDIO_HOME environment variable to a writable folder and restart.")
        return

    inject_theme()
    state.init_state()
    state.persist_widgets()
    render_sidebar()
    show_flash()

    page_id = state.current_page()
    page = next(p for p in state.PAGES if p.id == page_id)
    try:
        importlib.import_module(f"ui.pages.{page.module}").render()
    except Exception as exc:  # last line of defence: never show a raw stack trace to the user
        import logging

        logging.getLogger("ui").exception("Page %s crashed", page_id)
        banner("error", "Something went wrong on this page", f"{type(exc).__name__}: {exc}", ["The details were written to data/logs/app.log.", "Try another page, or reload the browser tab."])


main()
