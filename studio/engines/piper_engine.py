"""Piper offline neural TTS (https://github.com/OHF-Voice/piper1-gpl).

Voice models are plain ``.onnx`` + ``.onnx.json`` files placed in ``models/piper``. Nothing is
downloaded at runtime. Both the current (>=1.3) and the older Piper Python APIs are supported.
"""

from __future__ import annotations

import importlib.util
import json
import threading
from pathlib import Path

import numpy as np

from ..audio.types import AudioData
from ..config import get_paths
from ..errors import EngineError, EngineUnavailable
from .base import EngineStatus, SynthesisOptions, TTSEngine, VoiceInfo


class PiperEngine(TTSEngine):
    id = "piper"
    name = "Piper (offline neural TTS)"

    def __init__(self, models_dir: Path | None = None) -> None:
        self._models_dir_override = models_dir
        self._loaded: dict[str, object] = {}
        self._load_lock = threading.RLock()
        self._voice_cache: tuple[tuple, list[VoiceInfo]] | None = None

    # ------------------------------------------------------------------ discovery
    @property
    def models_dir(self) -> Path:
        return self._models_dir_override or get_paths().piper_models

    @staticmethod
    def is_installed() -> bool:
        return importlib.util.find_spec("piper") is not None

    def status(self) -> EngineStatus:
        if not self.is_installed():
            return EngineStatus(
                False,
                "Piper is not installed.",
                ("Install it with: uv pip install piper-tts", "Then restart the app."),
            )
        voices = self.list_voices()
        if not voices:
            return EngineStatus(
                False,
                "No Piper voice models found.",
                (
                    f"Copy .onnx and .onnx.json voice files into: {self.models_dir}",
                    "Or run once (needs internet): python scripts/download_voices.py",
                ),
            )
        return EngineStatus(True, f"{len(voices)} voice{'s' if len(voices) != 1 else ''} ready.")

    def list_voices(self) -> list[VoiceInfo]:
        files = sorted(self.models_dir.rglob("*.onnx")) if self.models_dir.exists() else []
        signature = tuple((str(f), f.stat().st_mtime_ns) for f in files)
        if self._voice_cache and self._voice_cache[0] == signature:
            return self._voice_cache[1]
        voices = [v for v in (self._read_voice(f) for f in files) if v is not None]
        voices.sort(key=lambda v: (v.language_name, v.name, v.quality))
        self._voice_cache = (signature, voices)
        return voices

    def get_voice(self, voice_id: str) -> VoiceInfo | None:
        return next((v for v in self.list_voices() if v.id == voice_id), None)

    def _read_voice(self, model: Path) -> VoiceInfo | None:
        config_path = model.with_name(model.name + ".json")
        if not config_path.exists():
            return None
        try:
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        stem = model.stem
        parts = stem.split("-")
        language = cfg.get("language", {}) or {}
        code = language.get("code") or parts[0]
        english, country = language.get("name_english"), language.get("country_english")
        language_name = f"{english} ({country})" if english and country else (english or code)
        quality = (cfg.get("audio", {}) or {}).get("quality") or (parts[-1] if len(parts) >= 3 else "unknown")
        voice_name = parts[1].replace("_", " ").title() if len(parts) >= 3 else stem

        gender = "unspecified"
        meta_path = model.with_name(stem + ".studio.json")
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                gender = str(meta.get("gender", gender)).lower()
                voice_name = str(meta.get("display_name", voice_name))
            except (OSError, json.JSONDecodeError):
                pass
        if gender not in ("female", "male"):
            gender = "unspecified"

        speaker_map = cfg.get("speaker_id_map") or {}
        count = int(cfg.get("num_speakers", 1) or 1)
        if speaker_map:
            speakers = tuple(sorted((int(i), str(n)) for n, i in speaker_map.items()))
        elif count > 1:
            speakers = tuple((i, f"Speaker {i + 1}") for i in range(count))
        else:
            speakers = ()

        return VoiceInfo(
            id=stem,
            name=voice_name,
            language_code=code,
            language_name=language_name,
            gender=gender,
            quality=str(quality),
            sample_rate=int((cfg.get("audio", {}) or {}).get("sample_rate", 22050)),
            engine_id=self.id,
            model_path=str(model),
            speakers=speakers,
        )

    # ------------------------------------------------------------------ synthesis
    def _load(self, voice: VoiceInfo):
        if not self.is_installed():
            raise EngineUnavailable("Piper is not installed. Run: uv pip install piper-tts")
        with self._load_lock:
            cached = self._loaded.get(voice.model_path)
            if cached is not None:
                return cached
            try:
                from piper import PiperVoice  # type: ignore

                loaded = PiperVoice.load(voice.model_path, config_path=voice.model_path + ".json")
            except Exception as exc:
                raise EngineError(f"Could not load voice '{voice.name}': {exc}") from exc
            self._loaded[voice.model_path] = loaded
            return loaded

    def synthesize(self, text: str, voice: VoiceInfo, options: SynthesisOptions) -> AudioData:
        text = text.strip()
        if not text:
            return AudioData(np.zeros(0, dtype=np.float32), voice.sample_rate)
        piper_voice = self._load(voice)
        speed = min(2.0, max(0.5, float(options.speed)))
        length_scale = 1.0 / speed
        speaker_id = options.speaker_id if voice.is_multispeaker else None
        try:
            if hasattr(piper_voice, "synthesize_wav"):
                return self._synthesize_current(piper_voice, text, length_scale, speaker_id, voice.sample_rate)
            return self._synthesize_legacy(piper_voice, text, length_scale, speaker_id, voice.sample_rate)
        except EngineError:
            raise
        except Exception as exc:
            raise EngineError(f"Piper could not synthesise this text: {exc}") from exc

    @staticmethod
    def _synthesize_current(piper_voice, text: str, length_scale: float, speaker_id, default_rate: int) -> AudioData:
        try:
            from piper import SynthesisConfig  # type: ignore
        except ImportError:  # pragma: no cover - layout differs between releases
            from piper.config import SynthesisConfig  # type: ignore
        config = SynthesisConfig(speaker_id=speaker_id, length_scale=length_scale)
        arrays: list[np.ndarray] = []
        rate = default_rate
        for chunk in piper_voice.synthesize(text, syn_config=config):
            rate = int(getattr(chunk, "sample_rate", rate))
            if hasattr(chunk, "audio_float_array"):
                arrays.append(np.asarray(chunk.audio_float_array, dtype=np.float32))
            elif hasattr(chunk, "audio_int16_array"):
                arrays.append(np.asarray(chunk.audio_int16_array, dtype=np.float32) / 32768.0)
            else:
                arrays.append(np.frombuffer(chunk.audio_int16_bytes, dtype="<i2").astype(np.float32) / 32768.0)
        samples = np.concatenate(arrays) if arrays else np.zeros(0, dtype=np.float32)
        return AudioData(samples, rate)

    @staticmethod
    def _synthesize_legacy(piper_voice, text: str, length_scale: float, speaker_id, default_rate: int) -> AudioData:
        rate = int(getattr(getattr(piper_voice, "config", None), "sample_rate", default_rate))
        raw = b"".join(piper_voice.synthesize_stream_raw(text, speaker_id=speaker_id, length_scale=length_scale))
        samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
        return AudioData(samples, rate)
