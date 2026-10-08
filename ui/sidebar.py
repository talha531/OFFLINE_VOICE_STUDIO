"""Sidebar: brand, navigation, engine status and privacy note."""

from __future__ import annotations

import streamlit as st

from studio.config import APP_NAME, APP_VERSION
from studio.services import health
from studio.services.jobs import get_job_manager

from . import state
from .components import esc, html
from .icons import logo


def _chip(dot: str, title: str, detail: str) -> str:
    return f'<div class="vs-chip"><span class="vs-dot {dot}"></span><div><b>{esc(title)}</b>{esc(detail)}</div></div>'


def render_sidebar() -> None:
    with st.sidebar:
        html(
            f'<div class="vs-brand"><div class="vs-brand-mark">{logo()}</div>'
            f'<div><div class="vs-brand-name">{esc(APP_NAME)}</div><div class="vs-brand-sub">v{esc(APP_VERSION)} · Local</div></div></div>'
            '<div class="vs-nav-label">Workspace</div>'
        )
        current = state.current_page()
        for page in state.PAGES:
            st.button(
                page.label,
                key=f"nav_{page.id}",
                icon=page.material_icon,
                type="primary" if page.id == current else "secondary",
                use_container_width=True,
                on_click=state.go,
                args=(page.id,),
            )

        chips = []
        job = get_job_manager().active()
        if job is not None:
            snap = job.snapshot()
            chips.append(_chip("busy", "Generating audio", f"{snap.completed}/{snap.total} parts" if snap.total else "Starting…"))
        ready = health.speech_ready()
        chips.append(_chip("ok" if ready else "warn", "Speech engine ready" if ready else "Setup needed", "Piper · offline" if ready else "See Settings → Engines"))
        chips.append(_chip("ok", "Private & offline", "Your data stays on this device"))
        html(f'<div class="vs-side-foot">{"".join(chips)}</div>')
