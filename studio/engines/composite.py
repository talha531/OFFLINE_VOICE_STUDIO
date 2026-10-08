"""Combines several offline TTS engines (Piper, MMS, ...) behind the single TTSEngine contract.

Voices from every *available* engine appear in one list, so the UI's language picker covers all
of them; ``synthesize`` is routed to the engine that owns the chosen voice.
"""

from __future__ import annotations

import logging

from ..audio.types import AudioData
from ..errors import EngineUnavailable
from .base import EngineStatus, SynthesisOptions, TTSEngine, VoiceInfo

log = logging.getLogger(__name__)


class CompositeTTSEngine(TTSEngine):
    id = "composite"
    name = "Offline speech engines"

    def __init__(self, engines: list[TTSEngine]) -> None:
        self._engines = list(engines)

    @property
    def engines(self) -> list[TTSEngine]:
        return list(self._engines)

    def _ready(self) -> list[tuple[TTSEngine, EngineStatus]]:
        ready = []
        for engine in self._engines:
            try:
                status = engine.status()
            except Exception:
                log.exception("Engine %s status check failed", engine.id)
                continue
            if status.available:
                ready.append((engine, status))
        return ready

    def status(self) -> EngineStatus:
        ready = self._ready()
        if ready:
            voices = len(self.list_voices())
            return EngineStatus(True, f"{voices} voice{'s' if voices != 1 else ''} ready from {len(ready)} engine{'s' if len(ready) != 1 else ''}.")
        messages, hints = [], []
        for engine in self._engines:
            try:
                s = engine.status()
            except Exception:
                continue
            messages.append(s.message)
            hints.extend(h for h in s.hints if h not in hints)
        return EngineStatus(False, messages[0] if messages else "No speech engine is available.", tuple(hints))

    def list_voices(self) -> list[VoiceInfo]:
        voices: list[VoiceInfo] = []
        for engine, _ in self._ready():
            try:
                voices.extend(engine.list_voices())
            except Exception:
                log.exception("Engine %s could not list voices", engine.id)
        voices.sort(key=lambda v: (v.language_name, v.name, v.quality))
        return voices

    def synthesize(self, text: str, voice: VoiceInfo, options: SynthesisOptions) -> AudioData:
        for engine in self._engines:
            if engine.id == voice.engine_id:
                return engine.synthesize(text, voice, options)
        raise EngineUnavailable(f"The engine for voice '{voice.name}' is not available.")
