"""Settings: defaults, engines and system checks, storage and data management, about."""

from __future__ import annotations

import streamlit as st

from studio.config import (
    APP_NAME,
    APP_VERSION,
    CHUNK_RANGE,
    MP3_BITRATES,
    OUTPUT_FORMATS,
    PAUSE_RANGE,
    PITCH_RANGE,
    SPEED_RANGE,
    VOLUME_RANGE,
    get_paths,
)
from studio.engines.registry import get_tts_engine
from studio.services import health, maintenance
from studio.storage import repository as repo

from .. import state
from ..compat import FULL_DF
from ..components import banner, check_rows, confirm_action, flash, html, key_values, page_header, panel, section
from ..formatting import fmt_size, plural


# ----------------------------------------------------------------------- defaults
def _defaults() -> None:
    current = repo.get_settings()
    with panel("set-defaults"):
        with st.form("settings_form", border=False):
            html('<div class="vs-section" style="margin-top:0"><h2>Voice defaults</h2></div>')
            a, b, c = st.columns(3)
            speed = a.slider("Default speed", *SPEED_RANGE, value=float(current["default_speed"]), step=0.05, format="%.2fx")
            pitch = b.slider("Default pitch", *PITCH_RANGE, value=float(current["default_pitch"]), step=0.5, format="%+.1f st")
            volume = c.slider("Default volume", *VOLUME_RANGE, value=float(current["default_volume_db"]), step=1.0, format="%+.0f dB")

            html('<div class="vs-section"><h2>Processing</h2></div>')
            a, b = st.columns(2)
            chunk = a.slider("Maximum characters per part", *CHUNK_RANGE, value=int(current["chunk_max_chars"]), step=50)
            pause = b.slider("Pause between parts (ms)", *PAUSE_RANGE, value=int(current["pause_ms"]), step=25)
            a, b = st.columns(2)
            normalize = a.toggle("Normalize loudness", value=bool(current["normalize"]))
            trim = b.toggle("Trim silence", value=bool(current["trim_silence"]))
            preview_chars = st.slider("Preview length (characters)", 120, 800, value=int(current["preview_chars"]), step=20)

            html('<div class="vs-section"><h2>Export</h2></div>')
            a, b = st.columns(2)
            formats = list(OUTPUT_FORMATS)
            fmt = a.selectbox("Default format", formats, index=formats.index(current["default_format"]) if current["default_format"] in formats else 0)
            rates = list(MP3_BITRATES)
            bitrate = b.selectbox("MP3 bitrate (kbps)", rates, index=rates.index(current["mp3_bitrate"]) if current["mp3_bitrate"] in rates else rates.index(192))

            html('<div class="vs-section"><h2>Workspace</h2></div>')
            a, b = st.columns(2)
            confirm_over = a.number_input("Ask before jobs longer than (characters)", 1000, 1_000_000, value=int(current["confirm_over_chars"]), step=1000)
            page_size = b.number_input("Library items per page", 4, 50, value=int(current["library_page_size"]), step=2)
            saved = st.form_submit_button("Save settings", type="primary", icon=":material/save:")
        if saved:
            repo.save_settings(
                {
                    "default_speed": float(speed),
                    "default_pitch": float(pitch),
                    "default_volume_db": float(volume),
                    "chunk_max_chars": int(chunk),
                    "pause_ms": int(pause),
                    "normalize": bool(normalize),
                    "trim_silence": bool(trim),
                    "preview_chars": int(preview_chars),
                    "default_format": fmt,
                    "mp3_bitrate": int(bitrate),
                    "confirm_over_chars": int(confirm_over),
                    "library_page_size": int(page_size),
                }
            )
            state.apply_default_settings(repo.get_settings())
            flash("Settings saved and applied to Text-to-Speech")
            st.rerun()

    with panel("set-reset"):
        html('<div class="vs-section" style="margin-top:0"><h2>Restore defaults</h2></div>')
        confirm_action(
            "Restore factory settings",
            "set_reset",
            "Reset every setting to its original value? Your audio, history and voices are not affected.",
            _reset_settings,
            confirm_label="Yes, restore",
            icon_material=":material/restart_alt:",
        )


def _reset_settings() -> None:
    repo.reset_settings()
    state.apply_default_settings(repo.get_settings())
    flash("Settings restored")


# ----------------------------------------------------------------------- system
def _system() -> None:
    section("System checks", "cpu")
    with panel("set-checks"):
        checks = health.run_checks()
        check_rows([(c.ok, c.label, c.detail) for c in checks])
        if not all(c.ok for c in checks if c.required):
            banner("warning", "Setup is incomplete", "Fix the items marked above, then restart the app (Ctrl+C in the terminal, run it again).")

    section("Installed voices", "mic")
    with panel("set-voices"):
        engine = get_tts_engine()
        voices = engine.list_voices()
        key_values([("Engines", engine.name), ("Piper folder", str(get_paths().piper_models)), ("MMS folder (more languages)", str(get_paths().piper_models.parent / "mms"))])
        if voices:
            st.dataframe(
                [
                    {
                        "Voice": v.name,
                        "Language": v.language_name,
                        "Gender": v.gender.title() if v.gender != "unspecified" else "-",
                        "Quality": v.quality.replace("_", " ").title(),
                        "Sample rate": f"{v.sample_rate:,} Hz",
                        "Speakers": len(v.speakers) or 1,
                    }
                    for v in voices
                ],
                hide_index=True,
                **FULL_DF,
            )
        else:
            banner(
                "info",
                "No voice models installed",
                "Copy Piper `.onnx`/`.onnx.json` files into the Piper folder (`python scripts/download_voices.py`), and/or add MMS languages with `python scripts/download_mms.py urd-script_arabic hin ara`.",
            )
        st.caption("Optional: add a `<voice>.studio.json` file next to a model with `{\"gender\": \"female\"}` to enable gender filtering for it.")


# ----------------------------------------------------------------------- storage
def _storage() -> None:
    paths = get_paths()
    summary = maintenance.storage_summary()
    section("Where your data lives", "database")
    with panel("set-storage"):
        key_values(
            [
                ("Data folder", str(paths.root)),
                ("Audio", f"{fmt_size(summary.audio)}"),
                ("Voice profiles", f"{fmt_size(summary.voices)}"),
                ("Database", f"{fmt_size(summary.database)}"),
                ("Temporary files", f"{fmt_size(summary.temp)}"),
                ("Voice models", f"{fmt_size(summary.models)}"),
            ]
        )
        st.caption("Set the VOICE_STUDIO_HOME environment variable before launching to keep data somewhere else.")

    section("Clean up", "trash")
    a, b = st.columns(2)
    with a, panel("set-clean-a"):
        st.markdown("**Temporary files**")
        st.caption("Scratch data left by interrupted jobs.")
        confirm_action("Delete temporary files", "set_temp", "Delete all temporary files?", lambda: flash(f"Freed {fmt_size(maintenance.clear_temp_files())}"), confirm_label="Yes, delete", icon_material=":material/cleaning_services:")
    with b, panel("set-clean-b"):
        st.markdown("**Generated audio**")
        st.caption("Removes every file in the Audio Library from disk. History stays.")
        confirm_action("Delete all generated audio", "set_audio", "Permanently delete every generated audio file? This cannot be undone.", lambda: flash(f"Deleted {plural(maintenance.delete_all_audio(), 'file')}"), confirm_label="Yes, delete everything")
    with panel("set-clean-c"):
        st.markdown("**History**")
        st.caption("Removes the record of past runs. Audio files stay.")
        confirm_action("Clear all history", "set_hist", "Delete every history entry?", lambda: (repo.clear_history(), flash("History cleared")), confirm_label="Yes, clear it")


# ------------------------------------------------------------------------- about
def _about() -> None:
    with panel("set-about"):
        html(f'<div class="vs-section" style="margin-top:0"><h2>{APP_NAME}</h2></div>')
        key_values([("Version", APP_VERSION), ("Speech engine", "Piper (offline neural TTS)"), ("Storage", "SQLite + local files"), ("Network use", "None at runtime")])
        banner(
            "success",
            "Private by design",
            "Text, recordings, voice profiles and generated audio never leave this computer. The app makes no network requests and sends no telemetry. The only optional online step is downloading voice models once with `scripts/download_voices.py`.",
        )
        st.markdown(
            "**Keyboard tips**\n\n"
            "- `Tab` / `Shift+Tab` move between controls; `Space` plays or pauses the focused audio player.\n"
            "- `R` in the browser reruns the app after you change files on disk."
        )


def render() -> None:
    page_header("Settings", "Defaults, engines, storage and privacy.", eyebrow="Workspace", icon_name="settings")
    st.radio(
        "View",
        ["defaults", "system", "storage", "about"],
        key="seg_set_view",
        horizontal=True,
        format_func={"defaults": "Defaults", "system": "Engines & system", "storage": "Storage & data", "about": "About"}.get,
        label_visibility="collapsed",
    )
    {"defaults": _defaults, "system": _system, "storage": _storage, "about": _about}[st.session_state["seg_set_view"]]()
