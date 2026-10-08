"""Engine contracts. The rest of the app only ever talks to these interfaces, so engines can be
swapped or added without touching the UI or pipeline."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from ..audio.types import AudioData


@dataclass(frozen=True)
class EngineStatus:
    """Whether an engine can run right now, and what to do if it cannot."""

    available: bool
    message: str
    hints: tuple[str, ...] = ()


@dataclass(frozen=True)
class VoiceInfo:
    """A ready-to-use voice exposed by a TTS engine."""

    id: str
    name: str
    language_code: str  # e.g. "en_US"
    language_name: str  # e.g. "English (United States)"
    gender: str  # "female" | "male" | "unspecified"
    quality: str
    sample_rate: int
    engine_id: str
    model_path: str
    speakers: tuple[tuple[int, str], ...] = ()  # (speaker_id, label) for multi-speaker models

    @property
    def language_family(self) -> str:
        return self.language_code.replace("-", "_").split("_")[0].lower()

    @property
    def is_multispeaker(self) -> bool:
        return len(self.speakers) > 1


@dataclass(frozen=True)
class SynthesisOptions:
    speed: float = 1.0
    speaker_id: int | None = None
    language: str | None = None


class TTSEngine(ABC):
    """An offline text-to-speech engine with a fixed set of installed voices."""

    id: str = "tts"
    name: str = "TTS engine"

    @abstractmethod
    def status(self) -> EngineStatus: ...

    @abstractmethod
    def list_voices(self) -> list[VoiceInfo]: ...

    @abstractmethod
    def synthesize(self, text: str, voice: VoiceInfo, options: SynthesisOptions) -> AudioData: ...


@dataclass
class SpeakerModel:
    """Artifacts a cloning engine produced for one voice profile."""

    engine_id: str
    model_path: str
    info: dict = field(default_factory=dict)


class CloningEngine(ABC):
    """An offline voice-cloning backend.

    A real implementation must (a) build a reusable speaker model from a reference recording
    and (b) synthesise arbitrary text in that voice. See ``docs/CLONING_INTEGRATION.md``.
    """

    id: str = "cloning"
    name: str = "Voice cloning engine"

    @abstractmethod
    def status(self) -> EngineStatus: ...

    @abstractmethod
    def supported_languages(self) -> list[str]:
        """Language-family codes such as ``["en", "es"]``."""

    @abstractmethod
    def create_speaker_model(self, reference_wav: Path, output_dir: Path, language: str | None) -> SpeakerModel:
        """Analyse ``reference_wav`` and write reusable artifacts into ``output_dir``."""

    @abstractmethod
    def synthesize(self, text: str, model: SpeakerModel, options: SynthesisOptions) -> AudioData: ...
