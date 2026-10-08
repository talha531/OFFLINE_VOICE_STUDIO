"""Custom Voice: record or upload a reference, validate it, save a local profile, manage profiles.

Honesty rule: a profile can only *speak* when a real offline cloning engine is installed. Without
one, profiles are stored as validated references and every control says so.
"""

from __future__ import annotations


import streamlit as st

from studio.audio.validation import ReferenceReport
from studio.config import LANGUAGE_FAMILIES, SUPPORTED_AUDIO_TYPES
from studio.engines.registry import cloning_languages, get_cloning_engine, list_cloning_engines, plugin_load_errors
from studio.errors import StudioError
from studio.services import voice_profiles
from studio.services.pipeline import GenerationRequest, render_preview
from studio.audio.export import wav_bytes
from studio.storage import repository as repo

from .. import state
from ..compat import FULL
from ..components import (
    badge,
    badges,
    banner,
    card,
    check_rows,
    confirm_action,
    empty_state,
    esc,
    flash,
    html,
    key_values,
    page_header,
    panel,
    score_ring,
    section,
)
from ..formatting import fmt_duration, fmt_when
from ..icons import icon
from ..player import bytes_player, file_player, mime_for

_LEVEL_TONE = {"excellent": "success", "good": "success", "fair": "warning", "poor": "danger"}
_TIPS = [
    "Record 15 to 60 seconds of natural, continuous speech in a quiet room.",
    "Keep the microphone a hand-span away and avoid clipping (peaks near 0 dB).",
    "One speaker only. No music, echo or background voices.",
    "Read varied sentences. Avoid long silences or whispering.",
]


# ---------------------------------------------------------------- reference intake
def _reference() -> tuple[bytes, str] | None:
    """The current reference (bytes, file name), from the active input method."""
    ss = st.session_state
    source = ss.get("u_cv_rec") if ss.get("seg_cv_method") == "record" else ss.get("u_cv_up")
    if source is None:
        return None
    return source.getvalue(), getattr(source, "name", "recording.wav") or "recording.wav"


@st.cache_data(show_spinner=False, max_entries=6)
def _analyze(data: bytes) -> dict:
    return voice_profiles.analyze_upload(data).to_dict()


def _render_report(report: ReferenceReport) -> None:
    items = "".join(
        f'<li class="{esc(i.severity)}">{icon({"error": "x-circle", "warning": "alert", "info": "info"}[i.severity])}<span>{esc(i.message)}</span></li>'
        for i in report.issues
    )
    html(
        f'<div class="vs-ring-wrap">{score_ring(report.score, report.level)}<ul class="vs-issues">{items}</ul></div>'
    )
    key_values(
        [
            ("Duration", fmt_duration(report.duration)),
            ("Sample rate", f"{report.sample_rate:,} Hz"),
            ("Channels", str(report.channels)),
            ("Peak level", f"{report.peak_dbfs:.1f} dBFS"),
            ("Average level", f"{report.rms_dbfs:.1f} dBFS"),
            ("Noise floor", f"{report.noise_floor_dbfs:.1f} dBFS"),
            ("Signal / noise", f"{report.snr_db:.0f} dB"),
            ("Clipping", f"{report.clipping_pct:.2f} %"),
            ("Speech content", f"{report.speech_ratio * 100:.0f} %"),
        ]
    )


def _save_profile() -> None:
    ss = st.session_state
    ref = _reference()
    ss["cv_error"] = None
    if ref is None:
        ss["cv_error"] = "Add a reference recording first."
        return
    try:
        profile_id = voice_profiles.create_profile(
            name=ss["p_cv_name"], language=ss["p_cv_lang"], data=ref[0], notes=ss["p_cv_notes"]
        )
    except StudioError as exc:
        ss["cv_error"] = str(exc)
        return
    except Exception as exc:
        ss["cv_error"] = f"Could not save the profile: {exc}"
        return
    ss["cv_created"] = profile_id
    ss["p_cv_profile"] = profile_id
    ss["p_cv_name"] = ""
    ss["p_cv_notes"] = ""
    flash("Voice profile saved on this computer")


def _create_view() -> None:
    ss = st.session_state
    section("1  Reference recording", "mic")
    with panel("cv-reference"):
        with st.expander("Recording tips"):
            for tip in _TIPS:
                st.markdown(f"- {tip}")
        methods = ["upload", "record"] if hasattr(st, "audio_input") else ["upload"]
        st.radio(
            "Reference source",
            methods,
            key="seg_cv_method",
            horizontal=True,
            format_func=lambda m: "Upload a file" if m == "upload" else "Record with microphone",
            label_visibility="collapsed",
        )
        if ss["seg_cv_method"] == "record" and "record" in methods:
            st.audio_input("Record your voice", key="u_cv_rec", help="Your browser will ask for microphone permission. Audio never leaves this computer.")
        else:
            st.file_uploader(
                "Upload a clear recording of the voice",
                type=list(SUPPORTED_AUDIO_TYPES),
                key="u_cv_up",
                help="WAV works everywhere. FLAC, OGG and MP3 need the optional 'soundfile' package.",
            )

    ref = _reference()
    if ref is None:
        empty_state(
            "mic",
            "No reference yet",
            "Upload or record a short sample of the voice you want to keep. It is checked for length, noise and clipping, and stored only on this computer.",
        )
        return
    data, filename = ref

    section("2  Quality check", "shield")
    report: ReferenceReport | None = None
    with panel("cv-quality"):
        try:
            with st.spinner("Analysing the recording…"):
                report = ReferenceReport.from_dict(_analyze(data))
        except StudioError as exc:
            banner("error", "This recording could not be read", str(exc), ["Use a WAV file for best compatibility.", "Re-record if the problem continues."])
        if report is not None:
            _render_report(report)
            bytes_player(data, mime_for(filename))

    section("3  Save as a local voice profile", "database")
    with panel("cv-save"):
        if ss.get("cv_error"):
            banner("error", "The profile was not saved", ss["cv_error"])
        if ss.get("cv_created") and repo.get_voice_profile(ss["cv_created"]):
            created = repo.get_voice_profile(ss["cv_created"])
            banner("success", f"“{created['name']}” is saved", "It is stored on this computer. Find it under My voices.")
        left, right = st.columns(2)
        left.text_input("Voice name", key="p_cv_name", placeholder="e.g. My narration voice", max_chars=60)
        clonable = cloning_languages()
        codes = sorted(LANGUAGE_FAMILIES, key=lambda c: (c not in clonable, LANGUAGE_FAMILIES[c]))
        state.select_valid("p_cv_lang", codes, "en")
        right.selectbox(
            "Spoken language",
            codes,
            key="p_cv_lang",
            format_func=lambda c: f"{LANGUAGE_FAMILIES[c]}  ✓" if c in clonable else LANGUAGE_FAMILIES[c],
            help="✓ = the installed cloning engine(s) can speak this language." if clonable else None,
        )
        if clonable and ss["p_cv_lang"] not in clonable:
            st.caption(f"⚠️ {LANGUAGE_FAMILIES[ss['p_cv_lang']]} cannot be cloned by the installed engine(s); the profile is saved as a reference only.")
        st.text_area("Notes (optional)", key="p_cv_notes", height=80, placeholder="Microphone, room, intended use…")
        usable = bool(report and report.usable)
        can_save = usable and bool(ss["p_cv_name"].strip())
        st.button("Create voice profile", key="cv_save", on_click=_save_profile, type="primary", disabled=not can_save, icon=":material/save:")
        if report is not None and not usable:
            st.caption("Fix the problems marked in red above before saving.")
        elif not ss["p_cv_name"].strip():
            st.caption("Give the voice a name to continue.")

        engine = get_cloning_engine()
        if not engine.status().available:
            banner(
                "info",
                "Saved as a reference profile",
                "No offline cloning engine is installed, so the profile keeps your validated recording but cannot generate speech yet. See the Engine tab.",
            )

    _preview_section()


# ----------------------------------------------------------------- speech preview
def _preview_clicked(profile_id: int) -> None:
    ss = st.session_state
    ss["cv_preview"] = None
    request = GenerationRequest(text=ss["p_cv_text"], mode="custom", profile_id=profile_id, title="Voice preview")
    try:
        audio = render_preview(request, 300)
        ss["cv_preview"] = {"wav": wav_bytes(audio), "profile": profile_id}
        ss["cv_preview_error"] = None
    except StudioError as exc:
        ss["cv_preview_error"] = str(exc)
    except Exception as exc:
        ss["cv_preview_error"] = f"Unexpected error: {exc}"


def _preview_section() -> None:
    ss = st.session_state
    section("4  Preview speech", "play")
    profiles = repo.list_voice_profiles()
    with panel("cv-preview"):
        if not profiles:
            st.caption("Create a voice profile above to preview it here.")
            return
        by_id = {p["id"]: p for p in profiles}
        state.select_valid("p_cv_profile", list(by_id))
        st.selectbox("Voice", list(by_id), key="p_cv_profile", format_func=lambda i: by_id[i]["name"])
        profile = by_id[ss["p_cv_profile"]]
        engine = get_cloning_engine(profile.get("engine_id"))
        status = engine.status()
        speakable = status.available and bool(profile.get("model_ready"))

        st.text_area("Sentence to speak", key="p_cv_text", height=90)
        if not speakable:
            banner(
                "warning",
                "This voice cannot speak yet",
                "Speech in a custom voice needs a real offline cloning engine and a speaker model. Nothing is simulated." if not status.available else "Build the speaker model for this profile under My voices.",
                list(status.hints) if not status.available else (),
            )
        if st.button("Preview in this voice", key="cv_preview_btn", type="primary", disabled=not speakable or not ss["p_cv_text"].strip(), icon=":material/play_circle:"):
            with st.spinner("Synthesising in the custom voice…"):
                _preview_clicked(int(profile["id"]))
        if ss.get("cv_preview_error"):
            banner("error", "Preview failed", ss["cv_preview_error"])
        if ss.get("cv_preview") and ss["cv_preview"]["profile"] == profile["id"]:
            bytes_player(ss["cv_preview"]["wav"])
        with st.expander("Play the original reference recording"):
            if not file_player(profile["reference_path"]):
                st.caption("The reference file is missing from disk.")


# --------------------------------------------------------------------- my voices
def _build_model(profile_id: int) -> None:
    try:
        voice_profiles.build_speaker_model(profile_id)
        flash("Speaker model built")
    except StudioError as exc:
        st.session_state["cv_error"] = str(exc)
    except Exception as exc:
        st.session_state["cv_error"] = f"Model build failed: {exc}"


def _delete_profile(profile_id: int) -> None:
    voice_profiles.delete_profile(profile_id)
    if st.session_state.get("cv_created") == profile_id:
        st.session_state["cv_created"] = None
    flash("Voice profile deleted")


def _mine_view() -> None:
    profiles = repo.list_voice_profiles()
    if not profiles:
        empty_state("user", "No voice profiles yet", "Create one in the Create voice tab. Profiles are stored only on this computer.")
        st.button("Create a voice", key="cv_empty_cta", on_click=lambda: st.session_state.__setitem__("seg_cv_view", "create"), type="primary")
        return
    if st.session_state.get("cv_error"):
        banner("error", "Something went wrong", st.session_state["cv_error"])
    engine_ok = get_cloning_engine().status().available
    for p in profiles:
        report = voice_profiles.profile_report(p)
        ready = bool(p.get("model_ready"))
        with card(f"voice-{p['id']}"):
            main, actions = st.columns([3, 1.4])
            with main:
                html(
                    f'<div class="vs-title">{esc(p["name"])}</div>'
                    + badges(
                        [
                            badge("Ready to speak" if ready else "Reference only", "success" if ready else "warning"),
                            badge(f"{(p['quality_level'] or 'unknown').title()} · {p['quality_score']}/100", _LEVEL_TONE.get(p["quality_level"], "neutral")),
                            badge(LANGUAGE_FAMILIES.get(p["language"] or "", p["language"] or "Language not set")),
                            badge(fmt_duration(p["duration"])),
                            badge(f"Created {fmt_when(p['created_at'])}"),
                        ]
                    )
                )
                if p.get("notes"):
                    st.caption(p["notes"])
            with actions:
                if ready:
                    st.button("Use in Text-to-Speech", key=f"cv_use_{p['id']}", on_click=state.go, args=("tts",), kwargs={"seg_tts_mode": "custom", "p_tts_profile": p["id"]}, type="primary", **FULL, icon=":material/graphic_eq:")
                elif engine_ok:
                    st.button("Build speaker model", key=f"cv_build_{p['id']}", on_click=_build_model, args=(p["id"],), **FULL, icon=":material/model_training:")
                confirm_action("Delete", f"cv_del_{p['id']}", f"Delete “{p['name']}” and its reference recording? This cannot be undone.", lambda i=p["id"]: _delete_profile(i))
            if st.toggle("Show reference and quality report", key=f"u_cv_show_{p['id']}"):
                if not file_player(p["reference_path"]):
                    banner("error", "Reference file missing", "The recording was moved or deleted from the voices folder.")
                if report:
                    for issue in report.issues:
                        st.caption(f"{'⚠️' if issue.severity != 'info' else 'ℹ️'} {issue.message}")


# ---------------------------------------------------------------------- engine
def _engine_view() -> None:
    section("Voice-cloning engine", "cpu")
    engines = list_cloning_engines()
    with panel("cv-engine"):
        active = get_cloning_engine()
        status = active.status()
        if status.available:
            banner("success", f"Active engine: {active.name}", status.message)
        else:
            banner("warning", status.message, "Without an engine, profiles are saved as validated references and cannot speak. This app never fakes cloned speech.", list(status.hints))
        if engines:
            check_rows([(e.status().available, e.name, e.status().message) for e in engines])
        errors = plugin_load_errors()
        for name, message in errors.items():
            banner("error", f"Plugin “{name}” failed to load", message)
    section("Add a real engine", "layers")
    with panel("cv-howto"):
        st.markdown(
            "**Bundled: Coqui XTTS-v2** (`studio/engines/plugins/xtts_engine.py`). Install once with "
            "`uv pip install -r requirements-cloning.txt` and `python scripts/download_xtts.py`, then restart. "
            "It clones English, Spanish, French, German, Italian, Portuguese, Polish, Turkish, Russian, Dutch, Czech, Arabic, "
            "Chinese, Hungarian, Korean, Japanese and Hindi (not Urdu). Non-commercial licence.\n\n"
            "Cloning backends are plugins. Drop one file into `studio/engines/plugins/`, restart the app, and it appears here.\n\n"
            "1. Copy `_template.py` to `my_engine.py`.\n"
            "2. Implement `status`, `supported_languages`, `create_speaker_model` and `synthesize` with a model that runs fully offline.\n"
            "3. Keep `ENGINE = MyEngine` at the bottom of the file.\n\n"
            "The full guide is in `docs/CLONING_INTEGRATION.md`."
        )


def render() -> None:
    page_header(
        "Custom Voice",
        "Record or upload a reference, check its quality, and keep reusable voice profiles on this computer.",
        eyebrow="Voices",
        icon_name="mic",
    )
    count = len(repo.list_voice_profiles())
    st.radio(
        "View",
        ["create", "mine", "engine"],
        key="seg_cv_view",
        horizontal=True,
        format_func=lambda v: {"create": "Create voice", "mine": f"My voices ({count})", "engine": "Engine"}[v],
        label_visibility="collapsed",
    )
    view = st.session_state["seg_cv_view"]
    if view == "create":
        _create_view()
    elif view == "mine":
        _mine_view()
    else:
        _engine_view()
