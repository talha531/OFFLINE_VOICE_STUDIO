"""TEMPLATE for a real offline voice-cloning backend.

This file is ignored by the loader (the leading underscore). To add a backend:

1. Copy this file to ``my_engine.py`` (no leading underscore) in this folder.
2. Implement ``status``, ``supported_languages``, ``create_speaker_model`` and ``synthesize``
   using an actual cloning model that runs fully offline (for example a locally installed
   zero-shot TTS model with speaker conditioning).
3. Keep ``ENGINE = MyEngine`` at the bottom. Restart the app: it appears in
   Settings -> Engines and in Custom Voice automatically.

Nothing below produces audio on its own - it is deliberately not a working engine.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from studio.audio.export import read_audio
from studio.audio.types import AudioData
from studio.engines.base import CloningEngine, EngineStatus, SpeakerModel, SynthesisOptions
from studio.errors import EngineUnavailable


class MyEngine(CloningEngine):
    id = "my-engine"  # unique, stored on each voice profile
    name = "My offline cloning model"

    def status(self) -> EngineStatus:
        # Report readiness honestly: package importable AND model weights present on disk.
        if importlib.util.find_spec("my_cloning_package") is None:
            return EngineStatus(False, "my_cloning_package is not installed.", ("uv pip install my_cloning_package",))
        return EngineStatus(True, "Ready.")

    def supported_languages(self) -> list[str]:
        return ["en"]

    def create_speaker_model(self, reference_wav: Path, output_dir: Path, language: str | None) -> SpeakerModel:
        reference = read_audio(reference_wav)  # AudioData: mono float32 + sample_rate
        output_dir.mkdir(parents=True, exist_ok=True)
        # 1. Run your model's speaker encoder on ``reference``.
        # 2. Save the embedding/conditioning file into ``output_dir``.
        raise EngineUnavailable("Template only - implement create_speaker_model().")

    def synthesize(self, text: str, model: SpeakerModel, options: SynthesisOptions) -> AudioData:
        # Load ``model.model_path`` and return AudioData(samples_float32, sample_rate).
        raise EngineUnavailable("Template only - implement synthesize().")


ENGINE = MyEngine
