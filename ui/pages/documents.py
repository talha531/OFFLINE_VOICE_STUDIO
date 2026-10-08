"""Documents: import PDF / DOCX / TXT / Markdown, clean, preview, edit, save, and send to speech."""

from __future__ import annotations

import streamlit as st

from studio.errors import StudioError
from studio.services import cleaning, extraction
from studio.services.chunking import chunk_text, estimate_seconds
from studio.services.language import detect_language, language_name
from studio.storage import repository as repo
from studio.config import MAX_UPLOAD_MB, SUPPORTED_DOCUMENT_TYPES

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
    key_values,
    page_header,
    panel,
    section,
)
from ..formatting import fmt_duration_words, fmt_when


def _options() -> cleaning.CleaningOptions:
    ss = st.session_state
    return cleaning.CleaningOptions(
        fix_hyphenation=bool(ss["p_doc_fix_hyphenation"]),
        join_lines=bool(ss["p_doc_join_lines"]),
        remove_page_numbers=bool(ss["p_doc_remove_page_numbers"]),
        strip_markdown=bool(ss["p_doc_strip_markdown"]),
        remove_urls=bool(ss["p_doc_remove_urls"]),
    )


# ------------------------------------------------------------------------ callbacks
def _on_upload() -> None:
    ss = st.session_state
    ss.pop("doc_error", None)
    uploaded = ss.get("u_doc_file")
    if uploaded is None:
        return
    try:
        doc = extraction.extract(uploaded.name, uploaded.getvalue())
    except StudioError as exc:
        ss["doc_error"] = str(exc)
        return
    ss["p_doc_strip_markdown"] = doc.kind == "md"
    ss["doc_raw"] = doc.text
    ss["doc_kind"] = doc.kind
    ss["doc_pages"] = doc.pages
    ss["doc_warnings"] = list(doc.warnings)
    ss["doc_id"] = None
    ss["p_doc_name"] = doc.name
    ss["p_doc_text"] = cleaning.clean_text(doc.text, _options())
    flash(f"Imported {doc.name}")


def _reclean() -> None:
    ss = st.session_state
    ss["p_doc_text"] = cleaning.clean_text(ss["doc_raw"], _options())
    flash("Cleaning applied to the original text")


def _close_doc() -> None:
    ss = st.session_state
    for key in ("doc_raw", "p_doc_text", "p_doc_name"):
        ss[key] = ""
    ss["doc_id"] = None
    ss["doc_warnings"] = []
    ss.pop("doc_pages", None)


def _open_saved(doc_id: int) -> None:
    ss = st.session_state
    doc = repo.get_document(doc_id)
    if not doc:
        return
    ss["doc_raw"] = doc["text"]
    ss["doc_kind"] = doc["kind"]
    ss["doc_pages"] = None
    ss["doc_warnings"] = []
    ss["doc_id"] = doc["id"]
    ss["p_doc_name"] = doc["name"]
    ss["p_doc_text"] = doc["text"]
    ss["seg_doc_view"] = "editor"


def _save() -> None:
    ss = st.session_state
    name = ss["p_doc_name"].strip() or "Untitled document"
    text = ss["p_doc_text"]
    if ss.get("doc_id"):
        repo.update_document(ss["doc_id"], text, name)
        flash("Document updated")
    else:
        ss["doc_id"] = repo.add_document(name, ss.get("doc_kind", "txt"), text)
        flash("Saved to your documents")


def _send_to_tts() -> None:
    ss = st.session_state
    name = ss["p_doc_name"].strip() or "Document"
    state.go(
        "tts",
        p_tts_text=ss["p_doc_text"],
        tts_source=name,
        p_tts_title=name.rsplit(".", 1)[0],
        tts_preview=None,
        tts_approved_sig=None,
        tts_outcome=None,
    )


def _delete(doc_id: int) -> None:
    repo.delete_document(doc_id)
    if st.session_state.get("doc_id") == doc_id:
        st.session_state["doc_id"] = None
    flash("Document deleted")


# ---------------------------------------------------------------------------- views
def _editor() -> None:
    ss = st.session_state
    st.file_uploader(
        "Import a document",
        type=list(SUPPORTED_DOCUMENT_TYPES),
        key="u_doc_file",
        on_change=_on_upload,
        help=f"PDF, DOCX, TXT or Markdown up to {MAX_UPLOAD_MB} MB. Scanned PDFs without text are not supported.",
    )
    if ss.get("doc_error"):
        banner("error", "Could not read this file", ss["doc_error"])

    if not ss["doc_raw"] and not ss["p_doc_text"]:
        empty_state(
            "document",
            "No document open",
            "Drop a PDF, Word, text or Markdown file above. The text is extracted and cleaned on this computer, "
            "then you can edit it before turning it into speech.",
        )
        return

    for warning in ss.get("doc_warnings", []):
        banner("warning", "Heads up", warning)

    left, right = st.columns([1.7, 1], gap="large")
    with left:
        with panel("doc-editor"):
            st.text_input("Document name", key="p_doc_name", placeholder="Name shown in your library")
            st.text_area("Document text", key="p_doc_text", height=460, help="Edit freely. Changes are only stored when you press Save.")
            text = ss["p_doc_text"]
            if len(text) > 250_000:
                banner("info", "Large document", "Editing very long text can feel slow. Consider splitting it into chapters.")

    with right:
        with panel("doc-actions"):
            html('<div class="vs-section" style="margin-top:0"><h2>Actions</h2></div>')
            st.button("Send to Text-to-Speech", key="doc_send", on_click=_send_to_tts, type="primary", **FULL, icon=":material/graphic_eq:", disabled=not text.strip())
            st.button("Save to documents" if not ss.get("doc_id") else "Update saved document", key="doc_save", on_click=_save, **FULL, icon=":material/save:", disabled=not text.strip())
            st.download_button("Download as .txt", data=text.encode("utf-8"), file_name=(ss["p_doc_name"].rsplit(".", 1)[0] or "document") + ".txt", mime="text/plain", key="doc_dl", **FULL, icon=":material/download:", disabled=not text.strip())
            st.button("Close document", key="doc_close", on_click=_close_doc, type="tertiary", **FULL)

        with panel("doc-clean"):
            html('<div class="vs-section" style="margin-top:0"><h2>Cleaning</h2></div>')
            st.toggle("Repair hyphenated line breaks", key="p_doc_fix_hyphenation")
            st.toggle("Join wrapped lines", key="p_doc_join_lines")
            st.toggle("Remove page numbers", key="p_doc_remove_page_numbers")
            st.toggle("Strip Markdown symbols", key="p_doc_strip_markdown")
            st.toggle("Remove web addresses", key="p_doc_remove_urls")
            st.button("Re-apply to original", key="doc_reclean", on_click=_reclean, **FULL, icon=":material/cleaning_services:", help="Cleans the original extracted text again. Your manual edits are replaced.")

    text = ss["p_doc_text"]
    section("Document details", "info")
    chunks = chunk_text(text, int(st.session_state["p_tts_chunk"])) if text.strip() else []
    detected = detect_language(text)
    pages = ss.get("doc_pages")
    key_values(
        [
            ("Type", ss["doc_kind"].upper()),
            ("Pages", str(pages) if pages else "-"),
            ("Characters", f"{len(text):,}"),
            ("Words", f"{len(text.split()):,}"),
            ("Language", language_name(detected) if detected else "Not detected"),
            ("Speech parts", f"{len(chunks):,}"),
            ("Estimated audio", fmt_duration_words(estimate_seconds(text, 1.0))),
        ]
    )
    with st.expander(f"Preview speech parts ({len(chunks):,})"):
        if not chunks:
            st.caption("Nothing to split yet.")
        for chunk in chunks[:40]:
            st.markdown(f"**{chunk.index + 1}.** {chunk.text}")
        if len(chunks) > 40:
            st.caption(f"Showing the first 40 of {len(chunks):,} parts.")


def _saved() -> None:
    st.text_input("Search documents", key="p_doc_search", placeholder="Search by name", label_visibility="collapsed")
    needle = st.session_state["p_doc_search"].strip().lower()
    docs = [d for d in repo.list_documents() if needle in d["name"].lower()]
    if not docs:
        empty_state(
            "folder",
            "No saved documents" if not needle else "No matches",
            "Import a file and press Save to keep it here for later." if not needle else "Try a different search.",
        )
        return
    for doc in docs:
        with card(f"doc-{doc['id']}"):
            top, actions = st.columns([3, 1.4])
            with top:
                html(
                    f'<div class="vs-title">{esc(doc["name"])}</div>'
                    + badges(
                        [
                            badge(doc["kind"].upper(), "accent"),
                            badge(f"{doc['char_count']:,} characters"),
                            badge(f"Updated {fmt_when(doc['updated_at'])}"),
                        ]
                    )
                )
            with actions:
                st.button("Open", key=f"doc_open_{doc['id']}", on_click=_open_saved, args=(doc["id"],), **FULL, icon=":material/edit:")
                confirm_action(
                    "Delete",
                    f"doc_del_{doc['id']}",
                    f"Delete “{doc['name']}”? This only removes the saved copy, not your original file.",
                    lambda i=doc["id"]: _delete(i),
                )


def render() -> None:
    page_header(
        "Documents",
        "Turn PDFs, Word files, text and Markdown into clean, speech-ready text. Extraction happens locally.",
        eyebrow="Library",
        icon_name="document",
    )
    st.radio(
        "View",
        ["editor", "saved"],
        key="seg_doc_view",
        horizontal=True,
        format_func=lambda v: "Import & edit" if v == "editor" else f"Saved documents ({len(repo.list_documents())})",
        label_visibility="collapsed",
    )
    if st.session_state["seg_doc_view"] == "editor":
        _editor()
    else:
        _saved()
