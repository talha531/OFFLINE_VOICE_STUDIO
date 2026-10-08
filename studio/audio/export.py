"""Reading and writing audio files (WAV via soundfile/wave, MP3 via lameenc)."""

from __future__ import annotations

import io
import wave
from pathlib import Path
from typing import BinaryIO

import numpy as np

from ..errors import AudioValidationError, ExportError
from .processing import resample
from .types import AudioData

# Sample rates the LAME encoder accepts.
_MP3_RATES = (8000, 11025, 12000, 16000, 22050, 24000, 32000, 44100, 48000)


def to_int16(samples: np.ndarray) -> np.ndarray:
    return (np.clip(samples, -1.0, 1.0) * 32767.0).astype(np.int16)


# ----------------------------------------------------------------------------- reading
def _read_wav_stdlib(source: BinaryIO) -> tuple[np.ndarray, int]:
    """Fallback WAV reader (PCM 8/16/24/32-bit) used when soundfile is unavailable."""
    with wave.open(source, "rb") as wf:
        channels, width, rate, frames = wf.getnchannels(), wf.getsampwidth(), wf.getframerate(), wf.getnframes()
        raw = wf.readframes(frames)
    if width == 1:
        data = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    elif width == 2:
        data = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif width == 3:
        b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
        value = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
        value = np.where(value & 0x800000, value - 0x1000000, value)
        data = value.astype(np.float32) / 8388608.0
    elif width == 4:
        data = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    else:
        raise AudioValidationError("Unsupported WAV sample width.")
    return data.reshape(-1, channels), rate


def read_audio_multichannel(source: bytes | str | Path | BinaryIO) -> tuple[np.ndarray, int]:
    """Return (samples shaped [frames, channels] float32, sample_rate)."""
    if isinstance(source, (bytes, bytearray)):
        source = io.BytesIO(source)
    try:
        import soundfile as sf  # type: ignore

        data, rate = sf.read(source, dtype="float32", always_2d=True)
        return data, int(rate)
    except ImportError:
        pass
    except Exception as exc:  # soundfile.LibsndfileError, RuntimeError, ...
        raise AudioValidationError(
            "This audio file could not be read. Please use WAV, FLAC, OGG or MP3."
        ) from exc
    # soundfile missing: stdlib fallback handles WAV only.
    try:
        if isinstance(source, (str, Path)):
            with open(source, "rb") as fh:
                data, rate = _read_wav_stdlib(fh)
        else:
            source.seek(0)
            data, rate = _read_wav_stdlib(source)
        return data, int(rate)
    except Exception as exc:
        raise AudioValidationError("This audio file could not be read. Please use a WAV file.") from exc


def read_audio(source: bytes | str | Path | BinaryIO) -> AudioData:
    data, rate = read_audio_multichannel(source)
    return AudioData(data.mean(axis=1), rate)


# ----------------------------------------------------------------------------- writing
def wav_bytes(audio: AudioData) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(audio.sample_rate)
        wf.writeframes(to_int16(audio.samples).tobytes())
    return buffer.getvalue()


def write_wav(path: Path, audio: AudioData) -> int:
    try:
        data = wav_bytes(audio)
        path.write_bytes(data)
        return len(data)
    except OSError as exc:
        raise ExportError(f"Could not write {path.name}: {exc.strerror or exc}") from exc


def mp3_bytes(audio: AudioData, bitrate_kbps: int = 192) -> bytes:
    try:
        import lameenc  # type: ignore
    except ImportError as exc:
        raise ExportError("MP3 export needs the 'lameenc' package. Run: uv pip install lameenc") from exc

    samples, rate = audio.samples, audio.sample_rate
    if rate not in _MP3_RATES:
        samples, rate = resample(samples, rate, 44100), 44100
    try:
        encoder = lameenc.Encoder()
        encoder.set_bit_rate(int(bitrate_kbps))
        encoder.set_in_sample_rate(int(rate))
        encoder.set_channels(1)
        encoder.set_quality(2)
        return bytes(encoder.encode(to_int16(samples).tobytes()) + encoder.flush())
    except Exception as exc:
        raise ExportError(f"MP3 encoding failed: {exc}") from exc


def write_mp3(path: Path, audio: AudioData, bitrate_kbps: int = 192) -> int:
    data = mp3_bytes(audio, bitrate_kbps)
    try:
        path.write_bytes(data)
    except OSError as exc:
        raise ExportError(f"Could not write {path.name}: {exc.strerror or exc}") from exc
    return len(data)
