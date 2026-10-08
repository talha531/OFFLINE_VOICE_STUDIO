"""Real offline voice cloning with Coqui XTTS-v2 (zero-shot speaker cloning).

How it works: ``create_speaker_model`` runs XTTS's speaker encoder on your reference recording and
stores the resulting conditioning latents (``speaker.pt``). ``synthesize`` then speaks any text in
that voice. Everything runs locally; no network access is used at runtime.

Setup (once):
    uv pip install -r requirements-cloning.txt
    python scripts/download_xtts.py          # ~2 GB, needs internet once

Languages supported by XTTS-v2: English, Spanish, French, German, Italian, Portuguese, Polish,
Turkish, Russian, Dutch, Czech, Arabic, Chinese, Hungarian, Korean, Japanese, Hindi.
Urdu is NOT supported by XTTS-v2 (use a standard MMS/Piper voice for Urdu instead).

LICENCE: XTTS-v2 weights use the Coqui Public Model License - non-commercial use only. Only clone
voices you have the right to use.
"""

from __future__ import annotations

import importlib.util
import sys
import threading
from pathlib import Path

import numpy as np

from studio.audio.types import AudioData
from studio.config import LANGUAGE_FAMILIES, get_paths
from studio.engines.base import CloningEngine, EngineStatus, SpeakerModel, SynthesisOptions
from studio.errors import EngineError, EngineUnavailable

# app language family -> XTTS language code
_XTTS_LANGUAGES = {
    "en": "en", "es": "es", "fr": "fr", "de": "de", "it": "it", "pt": "pt", "pl": "pl", "tr": "tr",
    "ru": "ru", "nl": "nl", "cs": "cs", "ar": "ar", "zh": "zh-cn", "hu": "hu", "ko": "ko", "ja": "ja", "hi": "hi",
}
_REQUIRED_FILES = ("config.json", "model.pth", "vocab.json")
_SPEAKER_FILE = "speaker.pt"
_PAUSE_SECONDS = 0.12


def _has(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ValueError, ImportError):  # already imported without a spec (e.g. embedded or stubbed)
        return module in sys.modules


class XttsEngine(CloningEngine):
    id = "xtts-v2"
    name = "Coqui XTTS-v2 (offline voice cloning)"

    def __init__(self, model_dir: Path | None = None) -> None:
        self._model_dir_override = model_dir
        self._model = None
        self._device = "cpu"
        self._lock = threading.RLock()

    # ------------------------------------------------------------------ discovery
    @property
    def model_dir(self) -> Path:
        return self._model_dir_override or (get_paths().piper_models.parent / "xtts")

    @staticmethod
    def dependencies_installed() -> bool:
        return _has("torch") and _has("TTS")

    def weights_present(self) -> bool:
        return all((self.model_dir / f).exists() for f in _REQUIRED_FILES)

    def status(self) -> EngineStatus:
        if not self.dependencies_installed():
            return EngineStatus(
                False,
                "XTTS-v2 cloning engine: packages not installed.",
                ("Double-click install_voice_cloning.bat (or run scripts/install_cloning.ps1)", "Then restart the app."),
            )
        if not self.weights_present():
            return EngineStatus(
                False,
                "XTTS-v2 cloning engine: model files not found.",
                ("Double-click install_voice_cloning.bat to download the model (~2 GB, internet once)", f"Model folder: {self.model_dir}"),
            )
        return EngineStatus(True, "Ready. Zero-shot cloning runs fully offline (CPU works; a GPU is much faster).")

    def supported_languages(self) -> list[str]:
        return sorted(_XTTS_LANGUAGES)

    # ------------------------------------------------------------------ model loading
    def _load(self):
        if not self.dependencies_installed():
            raise EngineUnavailable("XTTS needs torch and coqui-tts. Run: uv pip install -r requirements-cloning.txt")
        if not self.weights_present():
            raise EngineUnavailable(f"XTTS model files are missing in {self.model_dir}. Run: python scripts/download_xtts.py")
        with self._lock:
            if self._model is not None:
                return self._model
            try:
                import torch  # type: ignore
                from TTS.tts.configs.xtts_config import XttsConfig  # type: ignore
                from TTS.tts.models.xtts import Xtts  # type: ignore

                config = XttsConfig()
                config.load_json(str(self.model_dir / "config.json"))
                model = Xtts.init_from_config(config)
                model.load_checkpoint(config, checkpoint_dir=str(self.model_dir), eval=True)
                self._device = "cuda" if torch.cuda.is_available() else "cpu"
                model.to(self._device)
            except Exception as exc:
                raise EngineError(f"Could not load the XTTS model: {exc}") from exc
            self._model = model
            return model

    # ------------------------------------------------------------------ cloning
    def create_speaker_model(self, reference_wav: Path, output_dir: Path, language: str | None) -> SpeakerModel:
        model = self._load()
        try:
            import torch  # type: ignore

            output_dir.mkdir(parents=True, exist_ok=True)
            with self._lock:
                gpt_cond_latent, speaker_embedding = model.get_conditioning_latents(audio_path=[str(reference_wav)])
            target = output_dir / _SPEAKER_FILE
            torch.save(
                {"gpt_cond_latent": gpt_cond_latent.detach().cpu(), "speaker_embedding": speaker_embedding.detach().cpu()},
                target,
            )
        except EngineError:
            raise
        except Exception as exc:
            raise EngineError(f"Could not analyse the reference recording: {exc}") from exc
        return SpeakerModel(engine_id=self.id, model_path=str(target), info={"language": language})

    def synthesize(self, text: str, model: SpeakerModel, options: SynthesisOptions) -> AudioData:
        family = (options.language or "").replace("-", "_").split("_")[0].lower()
        xtts_language = _XTTS_LANGUAGES.get(family)
        if xtts_language is None:
            shown = LANGUAGE_FAMILIES.get(family, family or "this language")
            supported = ", ".join(LANGUAGE_FAMILIES.get(c, c) for c in sorted(_XTTS_LANGUAGES))
            raise EngineError(f"XTTS-v2 cannot speak {shown}. Supported languages: {supported}. Change the voice's language in Custom Voice.")
        text = text.strip()
        if not text:
            return AudioData(np.zeros(0, dtype=np.float32), 24000)

        xtts = self._load()
        try:
            import torch  # type: ignore

            latents = torch.load(model.model_path, map_location=self._device, weights_only=True)
            with self._lock:
                out = xtts.inference(
                    text=text,
                    language=xtts_language,
                    gpt_cond_latent=latents["gpt_cond_latent"].to(self._device),
                    speaker_embedding=latents["speaker_embedding"].to(self._device),
                    speed=min(2.0, max(0.5, float(options.speed))),
                    enable_text_splitting=True,
                )
            wav = np.asarray(out["wav"], dtype=np.float32).reshape(-1)
        except EngineError:
            raise
        except FileNotFoundError as exc:
            raise EngineError("This voice's speaker model file is missing. Rebuild it under Custom Voice > My voices.") from exc
        except Exception as exc:
            raise EngineError(f"XTTS could not synthesise this text: {exc}") from exc
        return AudioData(wav, 24000)


ENGINE = XttsEngine
