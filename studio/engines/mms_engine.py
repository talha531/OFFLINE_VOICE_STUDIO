"""Meta MMS-TTS: offline neural speech for 1,100+ languages (Urdu, Hindi, Arabic, ...).

Models are plain Hugging Face folders placed in ``models/mms/<code>/`` (see
``scripts/download_mms.py``). Nothing is downloaded at runtime and ``local_files_only=True`` is
enforced. Needs the optional packages in ``requirements-mms.txt`` (torch + transformers).

LICENCE NOTE: MMS-TTS models are CC-BY-NC 4.0 - free for non-commercial use only.
"""

from __future__ import annotations

import importlib.util
import json
import threading
from collections import OrderedDict
from pathlib import Path

import numpy as np

from ..audio.types import AudioData
from ..config import get_paths
from ..errors import EngineError, EngineUnavailable
from .base import EngineStatus, SynthesisOptions, TTSEngine, VoiceInfo
from .mms_catalog import describe

_WEIGHTS = ("model.safetensors", "pytorch_model.bin")
_MAX_LOADED = 2  # keep memory bounded when switching between languages


class MmsEngine(TTSEngine):
    id = "mms"
    name = "Meta MMS-TTS (offline, many languages)"

    def __init__(self, models_dir: Path | None = None) -> None:
        self._models_dir_override = models_dir
        self._loaded: OrderedDict[str, tuple[object, object]] = OrderedDict()
        self._lock = threading.RLock()

    @property
    def models_dir(self) -> Path:
        return self._models_dir_override or (get_paths().piper_models.parent / "mms")

    @staticmethod
    def dependencies_installed() -> bool:
        return all(importlib.util.find_spec(m) is not None for m in ("torch", "transformers"))

    # ------------------------------------------------------------------ discovery
    def list_voices(self) -> list[VoiceInfo]:
        folder = self.models_dir
        if not folder.exists():
            return []
        voices: list[VoiceInfo] = []
        for model_dir in sorted(p for p in folder.iterdir() if p.is_dir()):
            if not (model_dir / "config.json").exists() or not (model_dir / "vocab.json").exists():
                continue
            if not any((model_dir / w).exists() for w in _WEIGHTS):
                continue
            try:
                cfg = json.loads((model_dir / "config.json").read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            family, language_name = describe(model_dir.name)
            voices.append(
                VoiceInfo(
                    id=f"mms-{model_dir.name}",
                    name=f"MMS {language_name}",
                    language_code=family,
                    language_name=language_name,
                    gender="unspecified",
                    quality="mms",
                    sample_rate=int(cfg.get("sampling_rate", 16000)),
                    engine_id=self.id,
                    model_path=str(model_dir),
                )
            )
        voices.sort(key=lambda v: v.language_name)
        return voices

    def status(self) -> EngineStatus:
        voices = self.list_voices()
        if not voices:
            return EngineStatus(
                False,
                "No MMS language models found.",
                (
                    "Optional: adds Urdu, Hindi, Arabic and many more languages.",
                    "Run (needs internet once): python scripts/download_mms.py urd-script_arabic hin ara",
                    f"Models go into: {self.models_dir}",
                ),
            )
        if not self.dependencies_installed():
            return EngineStatus(
                False,
                f"{len(voices)} MMS language model(s) found, but torch/transformers are not installed.",
                ("Install with: uv pip install -r requirements-mms.txt", "Then restart the app."),
            )
        return EngineStatus(True, f"{len(voices)} language model{'s' if len(voices) != 1 else ''} ready.")

    # ------------------------------------------------------------------ synthesis
    def _load(self, voice: VoiceInfo):
        if not self.dependencies_installed():
            raise EngineUnavailable("MMS needs torch and transformers. Run: uv pip install -r requirements-mms.txt")
        with self._lock:
            if voice.model_path in self._loaded:
                self._loaded.move_to_end(voice.model_path)
                return self._loaded[voice.model_path]
            try:
                from transformers import AutoTokenizer, VitsModel  # type: ignore

                model = VitsModel.from_pretrained(voice.model_path, local_files_only=True)
                tokenizer = AutoTokenizer.from_pretrained(voice.model_path, local_files_only=True)
                model.eval()
            except Exception as exc:
                raise EngineError(f"Could not load the {voice.language_name} model: {exc}") from exc
            self._loaded[voice.model_path] = (model, tokenizer)
            while len(self._loaded) > _MAX_LOADED:
                self._loaded.popitem(last=False)
            return self._loaded[voice.model_path]

    def synthesize(self, text: str, voice: VoiceInfo, options: SynthesisOptions) -> AudioData:
        text = text.strip()
        if not text:
            return AudioData(np.zeros(0, dtype=np.float32), voice.sample_rate)
        model, tokenizer = self._load(voice)
        try:
            import torch  # type: ignore

            model.speaking_rate = min(2.0, max(0.5, float(options.speed)))
            inputs = tokenizer(text, return_tensors="pt")
            if inputs["input_ids"].shape[-1] == 0:  # nothing this model can pronounce (e.g. only symbols)
                return AudioData(np.zeros(0, dtype=np.float32), voice.sample_rate)
            torch.manual_seed(555)  # MMS is stochastic; a fixed seed keeps chunks consistent
            with torch.no_grad():
                waveform = model(**inputs).waveform
            samples = waveform[0].float().cpu().numpy().astype(np.float32)
            rate = int(getattr(model.config, "sampling_rate", voice.sample_rate))
            return AudioData(samples, rate)
        except Exception as exc:
            hint = ""
            if getattr(tokenizer, "is_uroman", False):
                hint = " This language needs the 'uroman' package: uv pip install uroman."
            raise EngineError(f"MMS could not synthesise this text: {exc}.{hint}") from exc
