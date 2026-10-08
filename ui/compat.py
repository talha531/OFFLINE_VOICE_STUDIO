"""Small compatibility layer for Streamlit API changes between releases.

Newer Streamlit versions replace ``use_container_width=True`` with ``width="stretch"``; the helper
picks whichever the installed version understands.
"""

from __future__ import annotations

import inspect

import streamlit as st


def full_width(func) -> dict:
    """Keyword arguments that make ``func``'s element fill its container."""
    try:
        params = inspect.signature(func).parameters
    except (TypeError, ValueError):
        params = {}
    if "width" in params:
        return {"width": "stretch"}
    return {"use_container_width": True}


FULL = full_width(st.button)  # buttons and download buttons
FULL_DF = full_width(st.dataframe)
