# Offline Voice Studio

A private, fully local text-to-speech workspace built with Python and Streamlit. Type or upload a
document, preview a few seconds, review, generate the full audio, and export WAV or MP3 - all on
your own computer. No accounts, no cloud, no telemetry.

* **Pages:** Dashboard, Text-to-Speech, Documents, Custom Voice, Audio Library, History, Settings
* **Inputs:** typed text, PDF, DOCX, TXT, Markdown (automatic extraction, cleaning, preview, editing)
* **Voices:** Standard Voice (Piper neural TTS) and Custom Voice profiles; language, voice, gender
  (where known), speaker, speed, pitch and volume controls
* **Workflow:** Preview -> Review -> Generate -> Export, with progress, cancellation, confirmations,
  empty / loading / success / error states
* **Large documents:** sentence-aware chunking, per-chunk synthesis, silence trimming, loudness
  normalisation, merged output, live progress and a clean cancel
* **Storage:** SQLite history and library, audio files and voice profiles under `data/`

> **Voice cloning.** Piper is a *standard* TTS engine and cannot clone. Cloning comes from a separate
> optional engine, **Coqui XTTS-v2**, included as a plugin (`studio/engines/plugins/xtts_engine.py`).
> Until you install it, Custom Voice saves your validated reference as a "Reference only" profile and
> says so plainly; the app never fakes cloned speech. See "Voice cloning setup" below.

---

## Quick start on Windows (PowerShell + uv)

1. Install [uv](https://docs.astral.sh/uv/) once (skip if you have it):

   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

   Open a **new** PowerShell window afterwards.

2. Unzip the project, open PowerShell in that folder and run the one-time setup:

   ```powershell
   .\scripts\setup_windows.ps1
   ```

   This creates `.venv` (Python 3.12), installs `requirements.txt`, and offers to download four
   starter voices (internet is needed only for this step).

3. Start the app:

   ```powershell
   .\scripts\run_studio.ps1
   ```

   Your browser opens at <http://localhost:8501>. You can also double-click `setup_windows.bat`
   and `run_studio.bat`.

If PowerShell blocks scripts, run once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
(or use the `.bat` files, which bypass the policy for that single run).

### Manual setup (any OS)

```powershell
uv venv --python 3.12 .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
uv pip install -r requirements.txt
python scripts/download_voices.py # one-time, needs internet
streamlit run app.py
```

### Voices

Piper voices are `.onnx` + `.onnx.json` file pairs in `models/piper/`.

```powershell
python scripts/download_voices.py --list                 # curated catalogue
python scripts/download_voices.py                        # 4 starter voices
python scripts/download_voices.py de_DE-thorsten-medium  # any key from rhasspy/piper-voices
```

You can also copy voice files into `models/piper/` by hand (works fully offline). Add an optional
`<voice>.studio.json` next to a voice, e.g. `{"gender": "female", "display_name": "Anna"}`, to enable
the gender filter for it.

### More languages: Urdu, Hindi, Arabic and 1,000+ others (Meta MMS)

Piper has voices for roughly 30 languages. For Urdu, Hindi, Arabic, Punjabi, Pashto, Bengali, Tamil
and many more, the app also includes an optional **MMS** engine. Both engines appear together:
every installed language shows up in the Language dropdown of Text-to-Speech.

```powershell
uv pip install torch --index-url https://download.pytorch.org/whl/cpu   # CPU PyTorch
uv pip install -r requirements-mms.txt
python scripts/download_mms.py urd-script_arabic hin ara   # Urdu, Hindi, Arabic (~140 MB each, once)
python scripts/download_mms.py --list                      # curated codes; any ISO 639-3 code works
```

Restart the app. The language is also auto-detected from your text (Urdu, Arabic, Persian, Hindi,
Bengali, Tamil, Thai and others by script). MMS voices have one voice per language with no gender
choice, and **MMS models are CC-BY-NC 4.0 - non-commercial use only**. Piper voices have their own
licences; check each model card.

### Voice cloning setup (Custom Voice)

This is what turns "Saved as a reference profile" into profiles that can actually speak.
**Easiest: double-click `install_voice_cloning.bat`** (installs PyTorch + XTTS-v2 and downloads the
model, about 2.5 GB, internet needed once, then verifies). Double-click `check_setup.bat` any time to
see which engines are ready. Manual steps:

```powershell
uv pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu   # or a CUDA build for a GPU
uv pip install -r requirements-cloning.txt
python scripts/download_xtts.py          # ~2 GB, internet needed once
```

Restart the app. Settings -> System checks and Custom Voice -> Engine show "Active engine: Coqui
XTTS-v2". Then in Custom Voice record or upload 10-30 seconds of clean speech, save the profile (the
speaker model is built automatically; for profiles saved earlier use **My voices -> Build speaker
model**), and use **Preview in this voice** or pick it in Text-to-Speech.

* Cloning languages: English, Spanish, French, German, Italian, Portuguese, Polish, Turkish, Russian,
  Dutch, Czech, Arabic, Chinese, Hungarian, Korean, Japanese, Hindi. **Urdu is not supported by
  XTTS-v2**; use a standard MMS voice for Urdu. Set the profile's language to one of the above.
* CPU works but is slow (roughly real-time or slower); a CUDA GPU is much faster.
* XTTS-v2 weights are under the Coqui Public Model License: **non-commercial use only**. Only clone
  voices you have permission to use.
* Packages (`coqui-tts`, PyTorch) are large and their versions move quickly; if installation fails,
  install into a fresh `.venv` using Python 3.11 or 3.12.

### Multilingual cloning (Chatterbox, 23 languages)

XTTS-v2 above covers 17 languages. **Chatterbox Multilingual** is a second, optional cloning engine
that adds Hebrew, Swahili, Malay, Greek, Danish, Finnish, Norwegian and Swedish (and also covers
Arabic, Hindi, Chinese, Japanese, Korean and the major European languages). Neither engine supports
Urdu cloning.

```powershell
uv pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
uv pip install -r requirements-chatterbox.txt
python scripts/download_chatterbox.py      # ~3.3 GB, internet needed once
```

Install **one** cloning engine per environment: `chatterbox-tts` and `coqui-tts` pin different
PyTorch/numpy/transformers versions and can conflict. If both are installed, the app automatically uses
the engine that supports each profile's language. In Custom Voice, languages the installed engine can
clone are marked with a check mark in the "Spoken language" list. Speed is applied by time-stretching
for Chatterbox. Check the model card for licence terms.

### MP3 export

MP3 uses the bundled `lameenc` package (no ffmpeg needed). If it is missing the app still exports
WAV and tells you what to install in Settings -> System checks.

---

## Using the app

| Page | What it does |
| --- | --- |
| **Dashboard** | Totals, recent activity, setup status and quick actions |
| **Text-to-Speech** | Choose text or a document, pick a voice, set speed/pitch/volume, **Preview**, review the chunks, **Generate** with live progress (cancel anytime), **Export** WAV/MP3 and play back |
| **Documents** | Upload PDF/DOCX/TXT/MD, clean (hyphenation, line joins, page numbers, Markdown, URLs), edit, then send to Text-to-Speech; saved documents are kept locally |
| **Custom Voice** | Record in the browser or upload a reference, quality check, save a local profile, preview, manage profiles; shows engine status honestly |
| **Audio Library** | Search, filter, favourite, play, download and delete generated audio |
| **History** | Every run including failures and cancellations; reuse a run's text and settings |
| **Settings** | Default controls, system checks, installed voices, storage locations, clean-up, privacy |

Tips: for long books use chunk size 400-600 characters; a 100,000-character document is
processed chunk by chunk, so memory stays flat and you can cancel at any time.

## Project layout

```
app.py                  Streamlit entry point
assets/theme.css        Design system (dark theme, cards, hover/animation, focus rings, responsive)
.streamlit/config.toml  Theme + server defaults
models/piper/           Piper voices (.onnx + .onnx.json)
data/                   Created at first run: studio.db, audio/, voices/, logs/, tmp/
scripts/                setup_windows.ps1, run_studio.ps1, download_voices.py, download_mms.py, download_xtts.py, download_chatterbox.py, download_chatterbox.py
docs/                   ARCHITECTURE.md, CLONING_INTEGRATION.md
studio/                 Pure Python core - never imports Streamlit
  config.py errors.py bootstrap.py
  engines/              base interfaces, Piper + MMS engines, composite router, cloning placeholder, plugin registry
  audio/                processing, validation, waveform, WAV/MP3 export
  services/             extraction, cleaning, language, chunking, pipeline, jobs, voice profiles, health
  storage/              SQLite schema + repository
ui/                     Streamlit layer (state, components, sidebar, player, pages/)
tests/                  57 unit tests (stdlib unittest)
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the design.

## Privacy

Text, recordings, profiles and audio never leave your computer. The app makes no network requests and
sends no telemetry (`gatherUsageStats = false`). The only online steps are installing packages and
(optionally) downloading voices. Set `VOICE_STUDIO_HOME` / `VOICE_STUDIO_MODELS` to relocate data and
models.

## Tests

```powershell
python -m unittest discover -s tests -t .
```

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| "Piper is not installed" | `uv pip install piper-tts`, restart. Use Python 3.11-3.12 if a wheel is missing for your version. |
| "No Piper voice models found" (first run) | Normal until voices are downloaded: `.venv\Scripts\python.exe scripts\download_voices.py` (English etc.) and `.venv\Scripts\python.exe scripts\download_mms.py urd-script_arabic hin ara` (Urdu, Hindi, Arabic), then restart |
| "No offline cloning engine is installed" | Follow "Voice cloning setup" above, then restart |
| MP3 option disabled | `uv pip install lameenc` |
| PDF yields no text | The PDF is probably scanned images; this MVP does not include OCR |
| Microphone recording blank | Allow the microphone for localhost in the browser, or upload a file instead |
| Port in use | `streamlit run app.py --server.port 8502` |
| Data folder not writable | Set `VOICE_STUDIO_HOME` to a writable folder |

## Known limitations

* Scanned/image PDFs need OCR (not included).
* Pitch is applied as a post-processing shift, so extreme values can sound processed.
* Cloning needs the optional XTTS-v2 install (large) and does not cover Urdu; quality depends on a clean reference recording.
