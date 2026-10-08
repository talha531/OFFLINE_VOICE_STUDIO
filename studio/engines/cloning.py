"""Placeholder cloning engine used when no real backend is installed.

It performs no synthesis and never pretends to. Its only job is to report, honestly, that
voice cloning is unavailable and to point at the integration guide.
"""

from __future__ import annotations

from pathlib import Path

from ..audio.types import AudioData
from ..errors import EngineUnavailable
from .base import CloningEngine, EngineStatus, SpeakerModel, SynthesisOptions

_MESSAGE = "No voice-cloning engine is installed."


class NullCloningEngine(CloningEngine):
    id = "none"
    name = "No cloning engine"

    def status(self) -> EngineStatus:
        return EngineStatus(
            False,
            _MESSAGE,
            (
                "Voice profiles can still be recorded, validated and stored locally.",
                "Speech in a cloned voice needs a real offline cloning model plugged in.",
                "Install real cloning with one double-click: install_voice_cloning.bat (about 2.5 GB, internet needed once), then restart the app.",
                "Or write your own backend: docs/CLONING_INTEGRATION.md.",
            ),
        )

    def supported_languages(self) -> list[str]:
        return []

    def create_speaker_model(self, reference_wav: Path, output_dir: Path, language: str | None) -> SpeakerModel:
        raise EngineUnavailable(_MESSAGE)

    def synthesize(self, text: str, model: SpeakerModel, options: SynthesisOptions) -> AudioData:
        raise EngineUnavailable(_MESSAGE)
