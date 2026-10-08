"""Real offline voice cloning in 23 languages with Chatterbox Multilingual (Resemble AI).

``create_speaker_model`` analyses your reference recording and stores the conditioning data
(``speaker.pt``); ``synthesize`` speaks any text in that voice. Fully local at runtime.

Languages: Arabic, Danish, German, Greek, English, Spanish, Finnish, French, Hebrew, Hindi,
Italian, Japanese, Korean, Malay, Dutch, Norwegian, Polish, Portuguese, Russian, Swedish,
Swahili, Turkish, Chinese. Urdu is not supported.

Setup (once):
    uv pip install -r requirements-chatterbox.txt
    python scripts/download_chatterbox.py       # ~3.3 GB, needs internet once

Install either this engine or XTTS-v2 (or both in separate environments): their pinned
dependencies can conflict. When both are installed the app picks the one that supports the
profile's language. Check the model card for the current licence terms.
"""

from __future__ import annotations

import importlib.util
import sys
import threading
from pathlib import Path

import numpy as np

from studio.audio.processing import change_speed
from studio.audio.types import AudioData
from studio.config import LANGUAGE_FAMILIES, get_paths
from studio.engines.base import CloningEngine, EngineStatus, SpeakerModel, SynthesisOptions
from studio.errors import EngineError, EngineUnavailable

_LANGUAGES = (
    "ar", "da", "de", "el", "en", "es", "fi", "fr", "he", "hi", "it", "ja",
    "ko", "ms", "nl", "no", "pl", "pt", "ru", "sv", "sw", "tr", "zh",
)
_T3_FILE = "t3_mtl23ls_v2.safetensors"
_REQUIRED_FILES = ("ve.pt", "s3gen.pt", _T3_FILE, "grapheme_mtl_merged_expanded_v1.json")
_SPEAKER_FILE = "speaker.pt"


def _has(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ValueError, ImportError):
        return module in sys.modules


class ChatterboxEngine(CloningEngine):
    id = "chatterbox-mtl"
    name = "Chatterbox Multilingual (offline voice cloning, 23 languages)"

    def __init__(self, model_dir: Path | None = None) -> None:
        self._model_dir_override = model_dir
        self._model = None
        self._device = "cpu"
        self._lock = threading.RLock()

    @property
    def model_dir(self) -> Path:
        return self._model_dir_override or (get_paths().piper_models.parent / "chatterbox")

    @staticmethod
    def dependencies_installed() -> bool:
        return _has("torch") and _has("chatterbox")

    def weights_present(self) -> bool:
        return all((self.model_dir / f).exists() for f in _REQUIRED_FILES)

    def status(self) -> EngineStatus:
        if not self.dependencies_installed():
            return EngineStatus(
                False,
                "Chatterbox cloning engine: packages not installed.",
                ("Install: uv pip install -r requirements-chatterbox.txt", "Then restart the app."),
            )
        if not self.weights_present():
            return EngineStatus(
                False,
                "Chatterbox cloning engine: model files not found.",
                ("Download once (needs internet, ~3.3 GB): python scripts/download_chatterbox.py", f"Model folder: {self.model_dir}"),
            )
        return EngineStatus(True, "Ready. Zero-shot cloning in 23 languages, fully offline (a GPU is strongly recommended).")

    def supported_languages(self) -> list[str]:
        return list(_LANGUAGES)

    # ------------------------------------------------------------------ loading
    def _load(self):
        if not self.dependencies_installed():
            raise EngineUnavailable("Chatterbox needs torch and chatterbox-tts. Run: uv pip install -r requirements-chatterbox.txt")
        if not self.weights_present():
            raise EngineUnavailable(f"Chatterbox model files are missing in {self.model_dir}. Run: python scripts/download_chatterbox.py")
        with self._lock:
            if self._model is not None:
                return self._model
            try:
                import torch  # type: ignore
                from chatterbox.mtl_tts import ChatterboxMultilingualTTS  # type: ignore

                self._device = "cuda" if torch.cuda.is_available() else "cpu"
                self._model = ChatterboxMultilingualTTS.from_local(str(self.model_dir), self._device)
            except Exception as exc:
                raise EngineError(f"Could not load the Chatterbox model: {exc}") from exc
            return self._model

    # ------------------------------------------------------------------ cloning
    def create_speaker_model(self, reference_wav: Path, output_dir: Path, language: str | None) -> SpeakerModel:
        model = self._load()
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            target = output_dir / _SPEAKER_FILE
            with self._lock:  # prepare_conditionals stores its result on the shared model object
                model.prepare_conditionals(str(reference_wav), exaggeration=0.5)
                model.conds.save(target)
        except EngineError:
            raise
        except Exception as exc:
            raise EngineError(f"Could not analyse the reference recording: {exc}") from exc
        return SpeakerModel(engine_id=self.id, model_path=str(target), info={"language": language})

    def synthesize(self, text: str, model: SpeakerModel, options: SynthesisOptions) -> AudioData:
        family = (options.language or "").replace("-", "_").split("_")[0].lower()
        if family not in _LANGUAGES:
            shown = LANGUAGE_FAMILIES.get(family, family or "this language")
            supported = ", ".join(LANGUAGE_FAMILIES.get(c, c) for c in _LANGUAGES)
            raise EngineError(f"Chatterbox cannot speak {shown}. Supported languages: {supported}. Change the voice's language in Custom Voice.")
        text = text.strip()
        engine = self._load()
        if not text:
            return AudioData(np.zeros(0, dtype=np.float32), int(getattr(engine, "sr", 24000)))
        try:
            from chatterbox.mtl_tts import Conditionals  # type: ignore

            conds = Conditionals.load(model.model_path, map_location=self._device)
            with self._lock:
                engine.conds = conds.to(self._device)
                wav = engine.generate(text, language_id=family)
            samples = np.asarray(wav.detach().cpu().numpy() if hasattr(wav, "detach") else wav, dtype=np.float32).reshape(-1)
            rate = int(getattr(engine, "sr", 24000))
        except EngineError:
            raise
        except FileNotFoundError as exc:
            raise EngineError("This voice's speaker model file is missing. Rebuild it under Custom Voice > My voices.") from exc
        except Exception as exc:
            raise EngineError(f"Chatterbox could not synthesise this text: {exc}") from exc
        return AudioData(change_speed(samples, float(options.speed)), rate)


ENGINE = ChatterboxEngine
