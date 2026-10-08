"""Reusable presentation components. Everything here is display-only HTML/CSS (styled by
``assets/theme.css``) except ``confirm_action``, which wraps a two-step destructive button.

All dynamic text is escaped. Backticks in ``inline()`` text become ``<code>``.
"""

from __future__ import annotations

import html as _html
import re
from contextlib import contextmanager
from typing import Callable, Iterable, Iterator, Sequence

import streamlit as st

from .icons import icon


# --------------------------------------------------------------------------- helpers
def esc(value: object) -> str:
    return _html.escape(str(value if value is not None else ""), quote=True)


def inline(text: object) -> str:
    """Escape ``text`` and turn `backtick` spans into <code>."""
    safe = esc(text)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", safe)


def html(markup: str) -> None:
    """Render trusted HTML. Lines are joined so Markdown never mistakes indentation for code."""
    compact = "".join(line.strip() for line in markup.strip().splitlines())
    st.markdown(compact, unsafe_allow_html=True)


def _slug(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", str(text)).strip("-").lower() or "x"


@contextmanager
def card(name: str) -> Iterator[None]:
    """A hoverable surface that can hold widgets. ``name`` must be unique on the page."""
    with st.container(key=f"card-{_slug(name)}"):
        yield


@contextmanager
def panel(name: str) -> Iterator[None]:
    """A static (non-hover) surface that can hold widgets."""
    with st.container(key=f"panel-{_slug(name)}"):
        yield


# ------------------------------------------------------------------------ typography
def page_header(title: str, subtitle: str = "", eyebrow: str = "", icon_name: str = "") -> None:
    top = f'<div class="vs-eyebrow">{icon(icon_name) if icon_name else ""}{esc(eyebrow)}</div>' if eyebrow else ""
    sub = f"<p>{inline(subtitle)}</p>" if subtitle else ""
    html(f'<header class="vs-page-head">{top}<h1>{esc(title)}</h1>{sub}</header>')


def section(title: str, icon_name: str = "", hint: str = "") -> None:
    hint_html = f"<small>{esc(hint)}</small>" if hint else ""
    html(f'<div class="vs-section">{icon(icon_name) if icon_name else ""}<h2>{esc(title)}</h2>{hint_html}</div>')


def muted(text: str) -> None:
    html(f'<div class="vs-muted">{inline(text)}</div>')


# --------------------------------------------------------------------------- elements
def badge(text: str, tone: str = "neutral", icon_name: str = "") -> str:
    """Return badge markup (compose several inside ``badges()``)."""
    mark = icon(icon_name, 12) if icon_name else ""
    return f'<span class="vs-badge {esc(tone)}">{mark}{esc(text)}</span>'


def badges(items: Iterable[str]) -> str:
    return f'<div class="vs-badges">{"".join(items)}</div>'


_BANNER_ICONS = {"info": "info", "success": "check-circle", "warning": "alert", "error": "x-circle"}


def banner(kind: str, title: str, body: str = "", items: Sequence[str] = ()) -> None:
    """Inline status message. ``kind``: info | success | warning | error."""
    role = "alert" if kind == "error" else "status"
    body_html = f"<div>{inline(body)}</div>" if body else ""
    list_html = f"<ul>{''.join(f'<li>{inline(i)}</li>' for i in items)}</ul>" if items else ""
    html(
        f'<div class="vs-banner {esc(kind)}" role="{role}">{icon(_BANNER_ICONS.get(kind, "info"))}'
        f"<div><b>{esc(title)}</b>{body_html}{list_html}</div></div>"
    )


def empty_state(icon_name: str, title: str, message: str) -> None:
    html(
        f'<div class="vs-empty"><div class="vs-empty-icon">{icon(icon_name)}</div>'
        f"<h3>{esc(title)}</h3><p>{inline(message)}</p></div>"
    )


def stat_tiles(tiles: Sequence[tuple[str, str, str, str]]) -> None:
    """``tiles``: (icon_name, label, value, hint)."""
    cells = "".join(
        f'<div class="vs-tile" style="animation-delay:{i * 0.05:.2f}s">'
        f'<div class="vs-tile-top"><span>{esc(label)}</span>{icon(ic)}</div>'
        f'<div class="vs-tile-value">{esc(value)}</div><div class="vs-tile-hint">{esc(hint)}</div></div>'
        for i, (ic, label, value, hint) in enumerate(tiles)
    )
    html(f'<div class="vs-tiles">{cells}</div>')


def stepper(steps: Sequence[tuple[str, str]], current: int) -> None:
    """Workflow indicator. ``steps``: (title, subtitle). Steps before ``current`` show as done."""
    cells = []
    for i, (title, sub) in enumerate(steps):
        state = "done" if i < current else ("current" if i == current else "")
        mark = icon("check", 14) if state == "done" else str(i + 1)
        aria = ' aria-current="step"' if state == "current" else ""
        cells.append(
            f'<li class="vs-step {state}"{aria}><span class="vs-step-n">{mark}</span>'
            f'<span><span class="vs-step-t">{esc(title)}</span><br><span class="vs-step-s">{esc(sub)}</span></span></li>'
        )
    html(f'<ol class="vs-stepper" style="list-style:none;padding:0" aria-label="Workflow progress">{"".join(cells)}</ol>')


def progress_bar(fraction: float, title: str, right: str = "", sub: str = "", active: bool = True) -> None:
    pct = max(0.0, min(1.0, fraction)) * 100
    cls = "vs-bar" if active else "vs-bar static"
    sub_html = f'<div class="vs-progress-sub">{esc(sub)}</div>' if sub else ""
    html(
        f'<div class="vs-progress"><div class="vs-progress-head"><b>{esc(title)}</b><span>{esc(right)}</span></div>'
        f'<div class="{cls}" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{pct:.0f}" '
        f'aria-label="{esc(title)}"><i style="width:{pct:.1f}%"></i></div>{sub_html}</div>'
    )


def key_values(rows: Sequence[tuple[str, str]]) -> None:
    cells = "".join(f'<div><div class="k">{esc(k)}</div><div class="v">{esc(v)}</div></div>' for k, v in rows)
    html(f'<div class="vs-kv">{cells}</div>')


def score_ring(score: int, level: str) -> str:
    colour = {"excellent": "var(--green)", "good": "var(--teal)", "fair": "var(--amber)", "poor": "var(--red)"}.get(
        level, "var(--accent)"
    )
    return (
        f'<div class="vs-ring" style="--p:{int(score)};--c:{colour}" role="img" '
        f'aria-label="Quality score {int(score)} out of 100, {esc(level)}"><div><span>{int(score)}</span>'
        f"<small>{esc(level)}</small></div></div>"
    )


def check_rows(rows: Sequence[tuple[bool, str, str]]) -> None:
    """``rows``: (ok, title, detail). Detail may contain `code` spans."""
    cells = "".join(
        f'<div class="vs-check"><span class="vs-check-mark {"ok" if ok else "warn"}">'
        f'{icon("check" if ok else "alert")}</span><div><b>{esc(title)}</b>'
        f'<span class="d">{inline(detail)}</span></div></div>'
        for ok, title, detail in rows
    )
    html(f"<div>{cells}</div>")


def list_row(title: str, sub: str = "", end: str = "", badge_html: str = "") -> str:
    return (
        f'<div class="vs-row"><div class="vs-row-main"><div class="vs-row-title">{esc(title)}</div>'
        f'<div class="vs-row-sub">{esc(sub)}</div></div>{badge_html}<div class="vs-row-end">{esc(end)}</div></div>'
    )


# ----------------------------------------------------------------------- interactions
def flash(message: str, icon_name: str = "✅") -> None:
    """Queue a toast that survives the next rerun (e.g. after a button click)."""
    st.session_state.setdefault("_flash", []).append((message, icon_name))


def show_flash() -> None:
    for message, icon_char in st.session_state.pop("_flash", []):
        st.toast(message, icon=icon_char)


def confirm_action(
    label: str,
    key: str,
    message: str,
    on_confirm: Callable[[], None],
    *,
    confirm_label: str = "Yes, delete",
    icon_material: str = ":material/delete:",
    disabled: bool = False,
) -> None:
    """A button that needs a second, explicit confirmation before ``on_confirm`` runs."""
    flag = f"_confirm_{key}"
    if st.session_state.get(flag):
        banner("warning", "Please confirm", message)
        yes, no = st.columns(2)
        if yes.button(confirm_label, key=f"{key}_yes", type="primary", use_container_width=True):
            st.session_state[flag] = False
            on_confirm()
            st.rerun()
        if no.button("Keep it", key=f"{key}_no", use_container_width=True):
            st.session_state[flag] = False
            st.rerun()
    elif st.button(label, key=f"{key}_ask", icon=icon_material, disabled=disabled, use_container_width=True):
        st.session_state[flag] = True
        st.rerun()
