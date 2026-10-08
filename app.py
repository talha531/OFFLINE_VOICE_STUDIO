"""Offline Voice Studio - Cloud startup diagnostic."""

from __future__ import annotations

import importlib
import logging
import sys
import traceback
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


st.set_page_config(
    page_title="Offline Voice Studio",
    page_icon="🎙️",
    layout="wide",
)


def test_import(name, import_function):
    st.write(f"Testing `{name}`...")
    try:
        import_function()
        st.success(f"{name}: OK")
        return True
    except Exception:
        st.error(f"{name}: FAILED")
        st.code(traceback.format_exc())
        return False


def main() -> None:
    st.title("🎙️ Offline Voice Studio")
    st.write("Cloud startup diagnostic")

    st.write("Python:", sys.version)
    st.write("Platform:", sys.platform)
    st.write("Project:", str(ROOT))

    # ---------------------------------------------------------
    # Test imports
    # ---------------------------------------------------------

    if not test_import(
        "studio.bootstrap",
        lambda: import studio.bootstrap,
    ):
        return

    if not test_import(
        "studio.config",
        lambda: import studio.config,
    ):
        return

    if not test_import(
        "ui",
        lambda: import ui,
    ):
        return

    if not test_import(
        "ui.components",
        lambda: import ui.components,
    ):
        return

    if not test_import(
        "ui.sidebar",
        lambda: import ui.sidebar,
    ):
        return

    if not test_import(
        "ui.theme",
        lambda: import ui.theme,
    ):
        return

    # ---------------------------------------------------------
    # Import actual application components
    # ---------------------------------------------------------

    try:
        from studio.bootstrap import bootstrap
        from studio.config import APP_NAME
        from ui import state
        from ui.components import banner, show_flash
        from ui.sidebar import render_sidebar
        from ui.theme import inject_theme

        st.success("All application imports completed.")

    except Exception:
        st.error("Application imports failed.")
        st.code(traceback.format_exc())
        return

    # ---------------------------------------------------------
    # Test bootstrap
    # ---------------------------------------------------------

    st.write("Testing `bootstrap()`...")

    try:
        bootstrap()
        st.success("bootstrap(): OK")

    except Exception:
        st.error("bootstrap(): FAILED")
        st.code(traceback.format_exc())
        return

    st.success("Startup diagnostic completed successfully.")

    st.info(
        "If you can see this page on Streamlit Cloud, "
        "the problem is inside the normal application startup/page loading."
    )


if __name__ == "__main__":
    main()