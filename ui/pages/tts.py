"""Text-to-Speech: compose -> Preview -> Review -> Generate -> Export."""

from __future__ import annotations

import shutil
from pathlib import Path

import streamlit as st

from studio.errors import StudioError
from studio.services import cleaning, extraction
from studio.services.chunking import chunk_text, estimate_seconds
from studio.services.jobs import JobState, get_job_manager
from studio.services.language import detect_language, language_name
from studio.services.pipeline import GenerationRequest, render_preview
from studio.audio.export import wav_bytes
from studio.config import SUPPORTED_DOCUMENT_TYPES
from studio.storage import repository as repo

from .. import state
from ..compat import FULL
from ..components import (
    banner,
    flash,
    html,
    key_values,
    page_header,
    panel,
    progress_bar,
    section,
    stepper,
)
from ..formatting import fmt_duration, fmt_duration_words, fmt_size, plural
from ..icons import icon
from ..player import bytes_player, file_player
from ..request import audio_signature, build_request
from ..voice_panel import VoiceSelection, render_voice_panel

STEPS = (
    ("Preview", "Hear a short sample"),
    ("Review", "Approve the sound"),
    ("Generate", "Render the full audio"),
    ("Export", "Play, download, save"),
)
SAMPLE_TEXT = (
    "Welcome to Offline Voice Studio. Everything you hear is generated on this computer, "
    "with no internet connection and no cloud service.\n\n"
    "Paste an article, load a document, or type anything you like. Then choose a voice, "
    "listen to a short preview, and generate the full audio when it sounds right."
)


@st.cache_data(show_spinner=False, max_entries=8)
def _chunk_count(text: str, max_chars: int) -> int:
    return len(chunk_text(text, max_chars))


# -------------------------------------------------------------------- text import
def _import_upload() -> None:
    """on_change callback for the file uploader (runs before widgets are drawn)."""
    ss = st.session_state
    ss.pop("tts_import_error", None)
    uploaded = ss.get("u_tts_file")
    if uploaded is None:
        return
    try:
        doc = extraction.extract(uploaded.name, uploaded.getvalue())
        options = cleaning.CleaningOptions(strip_markdown=doc.kind == "md")
        ss["p_tts_text"] = cleaning.clean_text(doc.text, options)
        ss["tts_source"] = doc.name
        if not ss.get("p_tts_title"):
            ss["p_tts_title"] = Path(doc.name).stem
        flash(f"Loaded {doc.name}")
    except StudioError as exc:
        ss["tts_import_error"] = str(exc)


def _load_saved_document() -> None:
    ss = st.session_state
    doc_id = ss.get("p_tts_saved_doc")
    doc = repo.get_document(doc_id) if doc_id else None
    if doc:
        ss["p_tts_text"] = doc["text"]
        ss["tts_source"] = doc["name"]
        ss["p_tts_title"] = Path(doc["name"]).stem
        flash(f"Loaded {doc['name']}")


def _use_sample() -> None:
    st.session_state["p_tts_text"] = SAMPLE_TEXT
    st.session_state["tts_source"] = "Typed text"


def _clear_text() -> None:
    ss = st.session_state
    ss["p_tts_text"] = ""
    ss["p_tts_title"] = ""
    ss["tts_source"] = "Typed text"


def _text_panel() -> str:
    ss = st.session_state
    with panel("tts-text"):
        html(f'<div class="vs-section" style="margin-top:0">{icon("edit")}<h2>Text</h2></div>')
        st.text_input("Title (optional)", key="p_tts_title", placeholder="Used for the file name and in History")

        with st.expander("Import from a file or saved document"):
            kinds = list(SUPPORTED_DOCUMENT_TYPES)
            st.file_uploader(
                "Upload PDF, DOCX, TXT or Markdown",
                type=kinds,
                key="u_tts_file",
                on_change=_import_upload,
                help="The text is extracted and cleaned locally. You can edit it below.",
            )
            if ss.get("tts_import_error"):
                banner("error", "Could not import this file", ss["tts_import_error"])
            documents = repo.list_documents()
            if documents:
                names = {d["id"]: f"{d['name']}  ·  {d['char_count']:,} chars" for d in documents}
                state.select_valid("p_tts_saved_doc", list(names))
                st.selectbox("Saved documents", list(names), key="p_tts_saved_doc", format_func=lambda i: names[i])
                st.button("Load saved document", key="tts_load_doc", on_click=_load_saved_document)
            else:
                st.caption("Documents you save in the Documents page appear here.")

        st.text_area(
            "Text to speak",
            key="p_tts_text",
            height=320,
            placeholder="Type or paste the text you want to hear…",
            label_visibility="collapsed",
        )
        text = ss["p_tts_text"]
        if not text.strip():
            left, _ = st.columns([1, 2])
            left.button("Insert sample text", key="tts_sample", on_click=_use_sample, icon=":material/auto_awesome:")
            return text

        parts = _chunk_count(text, int(ss["p_tts_chunk"]))
        key_values(
            [
                ("Characters", f"{len(text):,}"),
                ("Words", f"{len(text.split()):,}"),
                ("Parts", f"{parts:,}"),
                ("Estimated audio", fmt_duration_words(estimate_seconds(text, float(ss['p_tts_speed'])))),
            ]
        )
        st.button("Clear text", key="tts_clear", on_click=_clear_text, type="tertiary", icon=":material/backspace:")
    return text


# ----------------------------------------------------------------------- job flow
def _consume_finished_job() -> None:
    """Move a finished background job's result into session state (once)."""
    ss = st.session_state
    job = get_job_manager().get(ss.get("tts_job_id"))
    if job is None:
        ss["tts_job_id"] = None
        return
    snap = job.snapshot()
    if not snap.finished:
        return
    ss["tts_job_id"] = None
    if snap.state == JobState.DONE and snap.result is not None:
        ss["tts_outcome"] = {"kind": "done", "result": snap.result}
        flash(f"Audio ready: {snap.title}")
    elif snap.state == JobState.CANCELLED:
        ss["tts_outcome"] = {"kind": "cancelled"}
    else:
        ss["tts_outcome"] = {"kind": "failed", "error": snap.error or "Something went wrong."}


def _start_job(request: GenerationRequest) -> None:
    ss = st.session_state
    job = get_job_manager().submit(request)
    ss["tts_job_id"] = job.id
    ss["tts_outcome"] = None
    ss["tts_confirm_long"] = False


def _cancel_job(job_id: str) -> None:
    get_job_manager().cancel(job_id)


@st.fragment(run_every=1.0)
def _job_progress(job_id: str) -> None:
    """Polls the background job once a second without re-running the whole page."""
    job = get_job_manager().get(job_id)
    if job is None:
        st.rerun()
        return
    snap = job.snapshot()
    if snap.finished:
        st.rerun()
        return
    if snap.state == JobState.QUEUED:
        title = "Waiting for an earlier job to finish"
    elif snap.state == JobState.CANCELLING:
        title = "Cancelling…"
    else:
        title = "Generating audio"
    right = f"{snap.completed} / {snap.total}" if snap.total else ""
    eta = f"About {fmt_duration_words(snap.eta)} left" if snap.eta else ""
    sub = f"{snap.message}  ·  {fmt_duration(snap.elapsed)} elapsed" + (f"  ·  {eta}" if eta else "")
    progress_bar(snap.percent, title, right, sub)
    st.button(
        "Cancel generation",
        key="tts_cancel",
        on_click=_cancel_job,
        args=(job_id,),
        icon=":material/stop_circle:",
        disabled=snap.state == JobState.CANCELLING,
    )


# ----------------------------------------------------------------------- workflow
def _stage(has_job: bool, outcome, preview_ok: bool, approved: bool) -> int:
    if outcome and outcome.get("kind") == "done":
        return 3
    if has_job or approved:
        return 2
    return 1 if preview_ok else 0


def _render_preview_clicked(request: GenerationRequest, signature: str) -> None:
    ss = st.session_state
    settings = repo.get_settings()
    try:
        with st.spinner("Rendering a short preview…"):
            audio = render_preview(request, int(settings["preview_chars"]))
    except StudioError as exc:
        ss["tts_preview"] = None
        ss["tts_preview_error"] = str(exc)
        return
    except Exception as exc:  # engine crash: show it instead of a stack trace
        ss["tts_preview"] = None
        ss["tts_preview_error"] = f"Unexpected error while rendering the preview: {exc}"
        return
    ss["tts_preview_error"] = None
    ss["tts_preview"] = {"sig": signature, "wav": wav_bytes(audio), "duration": audio.duration}
    ss["tts_approved_sig"] = None


def _approve(signature: str) -> None:
    st.session_state["tts_approved_sig"] = signature


def _unapprove() -> None:
    st.session_state["tts_approved_sig"] = None


def _summary(selection: VoiceSelection, request: GenerationRequest, parts: int) -> None:
    key_values(
        [
            ("Voice", selection.label or "-"),
            ("Language", language_name((selection.language or "").split("_")[0]) if selection.language else "-"),
            ("Speed", f"{request.speed:.2f}x"),
            ("Pitch", f"{request.pitch:+.1f} st"),
            ("Volume", f"{request.volume_db:+.0f} dB"),
            ("Parts", f"{parts:,}"),
            ("Formats", ", ".join(f.upper() for f in request.formats)),
        ]
    )


def _blockers(selection: VoiceSelection, has_text: bool, busy_elsewhere: bool) -> str:
    if not has_text:
        return "Enter or import some text to continue."
    if not selection.ready:
        return selection.problem or "Choose a voice to continue."
    if busy_elsewhere:
        return "Another generation is still running. Wait for it to finish or cancel it."
    return ""


def _language_hint(selection: VoiceSelection, text: str) -> None:
    if not selection.language or not text.strip():
        return
    detected = detect_language(text)
    voice_family = selection.language.replace("-", "_").split("_")[0].lower()
    if detected and detected != voice_family:
        banner(
            "info",
            f"This text looks like {language_name(detected)}",
            f"The selected voice speaks {language_name(voice_family)}. Pick a {language_name(detected)} voice for natural pronunciation.",
        )


def _export_panel(result, request_title: str) -> None:
    ss = st.session_state
    banner(
        "success",
        "Your audio is ready",
        f"{result.title} · {fmt_duration(result.duration)} · {plural(result.chunk_count, 'part')} · generated in {fmt_duration_words(result.elapsed)}.",
    )
    files = result.files
    tabs = st.tabs([f.format.upper() for f in files]) if len(files) > 1 else [st.container()]
    for tab, item in zip(tabs, files, strict=False):
        with tab:
            if not file_player(item.path):
                banner("error", "File not found", f"{item.path} was moved or deleted.")
                continue
            left, right = st.columns([1, 2])
            with left:
                st.download_button(
                    f"Download {item.format.upper()}  ({fmt_size(item.size_bytes)})",
                    data=Path(item.path).read_bytes(),
                    file_name=Path(item.path).name,
                    mime="audio/mpeg" if item.format == "mp3" else "audio/wav",
                    key=f"tts_dl_{item.audio_id}",
                    type="primary",
                    **FULL,
                    icon=":material/download:",
                )
            right.caption(f"Saved in your library: {item.path}")

    with st.expander("Save a copy to another folder"):
        ss.setdefault("p_tts_export_dir", str(Path.home() / "Downloads"))
        st.text_input("Destination folder", key="p_tts_export_dir")
        if st.button("Save copies here", key="tts_copy", icon=":material/folder_copy:"):
            try:
                target = Path(ss["p_tts_export_dir"]).expanduser()
                target.mkdir(parents=True, exist_ok=True)
                for item in files:
                    shutil.copy2(item.path, target / Path(item.path).name)
                banner("success", "Copied", f"{plural(len(files), 'file')} saved to {target}")
            except OSError as exc:
                banner("error", "Could not copy the files", exc.strerror or str(exc))

    left, right = st.columns(2)
    left.button(
        "Open in Audio Library",
        key="tts_open_lib",
        on_click=state.go,
        args=("library",),
        kwargs={"p_lib_search": result.title, "lib_page": 0},
        **FULL,
        icon=":material/library_music:",
    )
    right.button("Start a new generation", key="tts_new", on_click=_reset_flow, **FULL, icon=":material/add:")


def _reset_flow() -> None:
    ss = st.session_state
    ss["tts_outcome"] = None
    ss["tts_preview"] = None
    ss["tts_approved_sig"] = None
    ss["tts_confirm_long"] = False


def _dismiss_outcome() -> None:
    st.session_state["tts_outcome"] = None


def _workflow(selection: VoiceSelection, text: str, request: GenerationRequest) -> None:
    ss = st.session_state
    manager = get_job_manager()
    job_id = ss.get("tts_job_id")
    has_job = bool(job_id and manager.get(job_id))
    active = manager.active()
    busy_elsewhere = bool(active and (not job_id or active.id != job_id))
    outcome = ss.get("tts_outcome")
    has_text = bool(text.strip())

    signature = audio_signature(request) if has_text else ""
    preview = ss.get("tts_preview")
    preview_ok = bool(preview and has_text and preview["sig"] == signature)
    approved = preview_ok and ss.get("tts_approved_sig") == signature
    stage = _stage(has_job, outcome, preview_ok, approved)

    section("Preview, review, generate, export", "zap")
    stepper(STEPS, stage)

    with panel("tts-flow"):
        if outcome and outcome["kind"] == "done":
            _export_panel(outcome["result"], request.display_title)
            return

        if outcome and outcome["kind"] == "failed":
            banner("error", "Generation failed", outcome["error"], ["Nothing was added to the library.", "Check History for details, adjust settings and try again."])
            st.button("Dismiss", key="tts_dismiss_fail", on_click=_dismiss_outcome)
        elif outcome and outcome["kind"] == "cancelled":
            banner("info", "Generation cancelled", "Nothing was added to your library. The run is recorded in History.")
            st.button("Dismiss", key="tts_dismiss_cancel", on_click=_dismiss_outcome)

        if has_job:
            _job_progress(job_id)
            return

        blocker = _blockers(selection, has_text, busy_elsewhere)
        _language_hint(selection, text)

        # ---- stage 0 / 1: preview
        if stage <= 1:
            parts = _chunk_count(text, request.max_chars) if has_text else 0
            if preview and has_text and not preview_ok:
                banner("warning", "The preview is out of date", "The text or settings changed since it was rendered. Render a new preview to continue.")
            if ss.get("tts_preview_error"):
                banner("error", "Preview failed", ss["tts_preview_error"])
            if stage == 0:
                st.markdown("**Step 1 — Preview.** Render the opening of your text with these exact settings before committing to the full job.")
                if st.button(
                    "Render preview",
                    key="tts_preview_btn",
                    type="primary",
                    disabled=bool(blocker),
                    icon=":material/play_circle:",
                ):
                    _render_preview_clicked(request, signature)
                    st.rerun()
                if blocker:
                    st.caption(blocker)
                return

            st.markdown("**Step 2 — Review.** Listen, then approve it or change the voice and delivery above.")
            bytes_player(preview["wav"])
            _summary(selection, request, parts)
            left, right = st.columns(2)
            left.button("Approve and continue", key="tts_approve", on_click=_approve, args=(signature,), type="primary", **FULL, icon=":material/check_circle:")
            if right.button("Render again", key="tts_rerender", **FULL, icon=":material/refresh:"):
                _render_preview_clicked(request, signature)
                st.rerun()
            return

        # ---- stage 2: generate
        parts = _chunk_count(text, request.max_chars)
        st.markdown("**Step 3 — Generate.** The full audio is rendered in the background. You can leave this page and come back.")
        _summary(selection, request, parts)
        threshold = int(repo.get_settings()["confirm_over_chars"])
        is_long = len(text) > threshold

        if ss.get("tts_confirm_long") and is_long:
            banner(
                "warning",
                "This is a long job",
                f"{len(text):,} characters in {plural(parts, 'part')}, roughly {fmt_duration_words(estimate_seconds(text, request.speed))} of audio. It may take several minutes. You can cancel at any time.",
            )
            left, right = st.columns(2)
            if left.button("Start generating", key="tts_confirm_go", type="primary", **FULL, disabled=bool(blocker)):
                _start_job(request)
                st.rerun()
            right.button("Not yet", key="tts_confirm_no", on_click=lambda: ss.__setitem__("tts_confirm_long", False), **FULL)
            return

        left, right = st.columns([2, 1])
        if left.button(
            "Generate full audio",
            key="tts_generate",
            type="primary",
            **FULL,
            disabled=bool(blocker),
            icon=":material/graphic_eq:",
        ):
            if is_long:
                ss["tts_confirm_long"] = True
            else:
                _start_job(request)
            st.rerun()
        right.button("Back to review", key="tts_back", on_click=_unapprove, **FULL)
        if blocker:
            st.caption(blocker)


# ------------------------------------------------------------------------- page
def render() -> None:
    page_header(
        "Text-to-Speech",
        "Write or import text, choose a voice, preview it, then generate the full audio. All of it runs on this computer.",
        eyebrow="Studio",
        icon_name="tts",
    )
    _consume_finished_job()
    left, right = st.columns([1.55, 1], gap="large")
    with left:
        text = _text_panel()
    with right:
        selection = render_voice_panel()
    request = build_request(selection, text)
    _workflow(selection, text, request)
