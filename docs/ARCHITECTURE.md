# Architecture

Two layers with one rule: **`studio/` never imports Streamlit; `ui/` contains no business logic.**

```
ui/pages/*  ->  ui/components, ui/state, ui/player, ui/voice_panel
     |
     v
studio/services  (pipeline, jobs, extraction, cleaning, chunking, voice_profiles, health)
     |                    |
     v                    v
studio/engines      studio/audio            studio/storage (SQLite)
(Piper, cloning)    (process, validate,     (schema + repository)
                     export WAV/MP3)
```

## Generation flow (Preview -> Review -> Generate -> Export)

1. **Prepare** - `GenerationRequest` (text, voice, speed/pitch/volume, chunk size, formats).
   `prepare_chunks` splits at paragraph/sentence boundaries up to `chunk_max_chars`.
2. **Preview** - `render_preview` synthesises the first ~300 characters; the request signature is
   remembered so *Generate* is only enabled for the settings that were reviewed.
3. **Generate** - `JobManager` runs `run_generation` in a daemon thread (one job at a time). Each
   chunk is synthesised, processed (trim, normalise, pitch/volume), joined with pauses; progress
   and cancellation are checked between chunks. The UI polls `snapshot()`.
4. **Export** - WAV (stdlib `wave`) and MP3 (`lameenc`) written to `data/audio/`, recorded in
   SQLite (`audio_library` and `history` tables). Long jobs ask for confirmation above
   `confirm_over_chars`.

## Engines

* `TTSEngine` (Piper implementation): `status`, `list_voices`, `synthesize`. Supports the current
  and legacy Piper Python APIs. Voices are discovered from `models/piper/*.onnx`.
* `CloningEngine`: separate interface + plugin registry (see `CLONING_INTEGRATION.md`).
  `NullCloningEngine` is honest about being a placeholder.

## State and UI

* Navigation and widget state live in `st.session_state`; `ui/state.py` re-persists keyed inputs
  (`p_*`, `seg_*`) so values survive page switches.
* `assets/theme.css` is the design system: tokens, cards, sidebar, hover/focus states,
  reduced-motion support, responsive breakpoints. `ui/components.py` wraps repeated markup
  (page headers, banners, key-value rows, confirmations, empty states).
* Every page's `render()` is wrapped in a last-resort error boundary in `app.py`.

## Storage

`data/studio.db` (SQLite, WAL) holds settings, documents, voice profiles, audio library and
history. Files: `data/audio`, `data/voices` (references), `data/voice_models`, `data/logs/app.log`,
`data/tmp`. Everything is local; nothing is uploaded.

## Tests

`tests/` covers extraction, cleaning, chunking, audio processing/validation/export, the generation
pipeline with a fake engine (progress, cancellation, merging) and storage.
