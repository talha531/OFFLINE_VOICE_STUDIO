"""The generation pipeline: chunk -> synthesise -> post-process -> merge -> export -> record.

``render_preview`` and ``run_generation`` share the same synthesis and post-processing code
so a preview is a faithful sample of the final result.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np

from ..audio import processing as dsp
from ..audio.export import write_mp3, write_wav
from ..audio.types import AudioData
from ..config import get_paths
from ..engines.base import SpeakerModel, SynthesisOptions
from ..engines.registry import get_cloning_engine, get_tts_engine
from ..errors import EngineError, EngineUnavailable, JobCancelled, StudioError
from ..storage import repository as repo
from .chunking import Chunk, chunk_text

log = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int, str], None]


@dataclass
class GenerationRequest:
    text: str
    title: str = ""
    source: str = "Typed text"
    mode: str = "standard"  # "standard" | "custom"
    voice_id: str | None = None
    profile_id: int | None = None
    language: str | None = None
    speaker_id: int | None = None
    speed: float = 1.0
    pitch: float = 0.0
    volume_db: float = 0.0
    normalize: bool = True
    trim_silence: bool = True
    pause_ms: int = 250
    max_chars: int = 450
    formats: tuple[str, ...] = ("wav",)
    mp3_bitrate: int = 192

    def params(self) -> dict:
        return {
            "mode": self.mode,
            "voice_id": self.voice_id,
            "profile_id": self.profile_id,
            "language": self.language,
            "speaker_id": self.speaker_id,
            "speed": self.speed,
            "pitch": self.pitch,
            "volume_db": self.volume_db,
            "normalize": self.normalize,
            "trim_silence": self.trim_silence,
            "pause_ms": self.pause_ms,
            "max_chars": self.max_chars,
            "formats": list(self.formats),
        }

    @property
    def display_title(self) -> str:
        if self.title.strip():
            return self.title.strip()
        first = re.sub(r"\s+", " ", self.text.strip())[:48].strip()
        return (first + "…") if len(self.text.strip()) > 48 else (first or "Untitled")


@dataclass
class GeneratedFile:
    path: Path
    format: str
    size_bytes: int
    audio_id: int


@dataclass
class GenerationResult:
    title: str
    files: list[GeneratedFile]
    duration: float
    chunk_count: int
    sample_rate: int
    history_id: int
    voice_label: str
    elapsed: float


# ----------------------------------------------------------------------------- helpers
def prepare_chunks(request: GenerationRequest) -> list[Chunk]:
    return chunk_text(request.text, request.max_chars)


@dataclass
class _Backend:
    synthesize: Callable[[str], AudioData]
    label: str
    language: str | None


def _build_backend(request: GenerationRequest) -> _Backend:
    if request.mode == "custom":
        profile = repo.get_voice_profile(request.profile_id or -1)
        if profile is None:
            raise StudioError("The selected custom voice no longer exists.")
        engine = get_cloning_engine(profile.get("engine_id"))
        status = engine.status()
        if not status.available:
            raise EngineUnavailable(f"{status.message} Speech in a custom voice needs a real cloning engine.")
        if not profile.get("model_ready") or not profile.get("model_path"):
            raise EngineUnavailable(
                "This voice profile has no speaker model yet. Open Custom Voice > My voices and build one."
            )
        model = SpeakerModel(engine_id=engine.id, model_path=profile["model_path"])
        language = request.language or profile.get("language")
        options = SynthesisOptions(speed=request.speed, language=language)
        return _Backend(lambda t: engine.synthesize(t, model, options), f"{profile['name']} (custom)", language)

    engine = get_tts_engine()
    status = engine.status()
    if not status.available:
        raise EngineUnavailable(status.message)
    voice = next((v for v in engine.list_voices() if v.id == request.voice_id), None)
    if voice is None:
        raise StudioError("The selected voice is not installed any more. Pick another voice.")
    options = SynthesisOptions(speed=request.speed, speaker_id=request.speaker_id, language=voice.language_code)
    return _Backend(lambda t: engine.synthesize(t, voice, options), f"{voice.name} · {voice.language_code}", voice.language_code)


def _process_piece(audio: AudioData, request: GenerationRequest, sample_rate: int) -> np.ndarray:
    samples = audio.samples
    if audio.sample_rate != sample_rate:
        samples = dsp.resample(samples, audio.sample_rate, sample_rate)
    if abs(request.pitch) >= 0.01:
        samples = dsp.pitch_shift(samples, sample_rate, request.pitch)
    if request.trim_silence:
        samples = dsp.trim_silence(samples, sample_rate)
    return dsp.fade_edges(samples, sample_rate)


def _assemble(pieces: list[np.ndarray], pauses: list[int], request: GenerationRequest, sample_rate: int) -> AudioData:
    merged = dsp.concat_with_pauses(pieces, pauses, sample_rate)
    if request.normalize:
        merged = dsp.peak_normalize(merged, -1.0)
    merged = dsp.apply_gain_db(merged, request.volume_db)
    return AudioData(dsp.guard_peaks(merged), sample_rate)


def _pauses(chunks: list[Chunk], pause_ms: int) -> list[int]:
    return [pause_ms * 2 if c.ends_paragraph else pause_ms for c in chunks]


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()[:40] or "audio"


# ------------------------------------------------------------------------------ public
def render_preview(request: GenerationRequest, preview_chars: int = 300) -> AudioData:
    """Synthesise only the opening of the text with the exact settings of the final job."""
    small = chunk_text(request.text, min(request.max_chars, max(120, preview_chars)))
    if not small:
        raise StudioError("There is no text to preview.")
    chosen = small[:1]
    if len(small[0].text) < preview_chars // 2 and len(small) > 1:
        chosen = small[:2]
    backend = _build_backend(request)

    pieces: list[np.ndarray] = []
    rate: int | None = None
    for chunk in chosen:
        audio = backend.synthesize(chunk.text)
        if audio.is_empty:
            continue
        rate = rate or audio.sample_rate
        pieces.append(_process_piece(audio, request, rate))
    if not pieces or rate is None:
        raise EngineError("The engine returned no audio for this text.")
    return _assemble(pieces, _pauses(chosen, request.pause_ms), request, rate)


def run_generation(
    request: GenerationRequest,
    cancel_event: threading.Event | None = None,
    on_progress: ProgressCallback | None = None,
) -> GenerationResult:
    """Run a complete generation. Raises JobCancelled if ``cancel_event`` is set."""
    cancel_event = cancel_event or threading.Event()
    chunks = prepare_chunks(request)
    if not chunks:
        raise StudioError("There is no readable text to convert.")
    backend = _build_backend(request)
    started = time.monotonic()
    title = request.display_title

    history_id = repo.add_history(
        title=title,
        source=request.source,
        text=request.text,
        voice_mode=request.mode,
        voice_label=backend.label,
        voice_id=request.voice_id,
        profile_id=request.profile_id,
        language=backend.language,
        params=request.params(),
        chunk_count=len(chunks),
    )
    try:
        pieces: list[np.ndarray] = []
        used_chunks: list[Chunk] = []
        rate: int | None = None
        for i, chunk in enumerate(chunks):
            if cancel_event.is_set():
                raise JobCancelled("Cancelled by user.")
            audio = backend.synthesize(chunk.text)
            if not audio.is_empty:
                rate = rate or audio.sample_rate
                pieces.append(_process_piece(audio, request, rate))
                used_chunks.append(chunk)
            if on_progress:
                on_progress(i + 1, len(chunks), f"Synthesised part {i + 1} of {len(chunks)}")
        if not pieces or rate is None:
            raise EngineError("The engine returned no audio for this text.")
        if cancel_event.is_set():
            raise JobCancelled("Cancelled by user.")

        if on_progress:
            on_progress(len(chunks), len(chunks), "Merging and exporting…")
        final = _assemble(pieces, _pauses(used_chunks, request.pause_ms), request, rate)

        files = _export(request, final, title, backend, history_id)
        repo.update_history(
            history_id,
            status="done",
            finished_at=_now(),
            duration=final.duration,
            chunk_count=len(chunks),
        )
        return GenerationResult(
            title=title,
            files=files,
            duration=final.duration,
            chunk_count=len(chunks),
            sample_rate=rate,
            history_id=history_id,
            voice_label=backend.label,
            elapsed=time.monotonic() - started,
        )
    except JobCancelled:
        repo.update_history(history_id, status="cancelled", finished_at=_now(), error="Cancelled by user.")
        raise
    except Exception as exc:
        message = str(exc) if isinstance(exc, StudioError) else f"Unexpected error: {exc}"
        if not isinstance(exc, StudioError):
            log.exception("Generation failed")
        repo.update_history(history_id, status="failed", finished_at=_now(), error=message)
        raise


def _now() -> str:
    from ..storage.db import now_iso

    return now_iso()


def _export(
    request: GenerationRequest, audio: AudioData, title: str, backend: _Backend, history_id: int
) -> list[GeneratedFile]:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    base = f"{stamp}_{_slug(title)}"
    folder = get_paths().audio
    preview = re.sub(r"\s+", " ", request.text.strip())[:160]
    files: list[GeneratedFile] = []
    for fmt in request.formats:
        fmt = fmt.lower()
        path = folder / f"{base}.{fmt}"
        counter = 1
        while path.exists():
            counter += 1
            path = folder / f"{base}-{counter}.{fmt}"
        size = write_mp3(path, audio, request.mp3_bitrate) if fmt == "mp3" else write_wav(path, audio)
        audio_id = repo.add_audio(
            title=title,
            path=str(path),
            fmt=fmt,
            duration=audio.duration,
            size_bytes=size,
            voice_label=backend.label,
            language=backend.language,
            text_preview=preview,
            history_id=history_id,
        )
        files.append(GeneratedFile(path, fmt, size, audio_id))
    return files
