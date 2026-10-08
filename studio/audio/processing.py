"""Pure-numpy audio processing: gain, normalisation, trimming, merging and pitch shifting.

Speed is *not* handled here: engines apply it natively (Piper uses ``length_scale``) which
sounds far better than post-hoc time stretching.
"""

from __future__ import annotations

import numpy as np

EPS = 1e-9


def db_to_gain(db: float) -> float:
    return float(10.0 ** (db / 20.0))


def peak_dbfs(x: np.ndarray) -> float:
    if x.size == 0:
        return -120.0
    return float(20.0 * np.log10(max(float(np.max(np.abs(x))), EPS)))


def apply_gain_db(x: np.ndarray, db: float) -> np.ndarray:
    if not db:
        return x
    return (x * db_to_gain(db)).astype(np.float32)


def peak_normalize(x: np.ndarray, target_dbfs: float = -1.0) -> np.ndarray:
    """Scale so the loudest sample sits at ``target_dbfs``. Silent input is returned unchanged."""
    peak = float(np.max(np.abs(x))) if x.size else 0.0
    if peak < 1e-6:
        return x
    return (x * (db_to_gain(target_dbfs) / peak)).astype(np.float32)


def guard_peaks(x: np.ndarray, ceiling: float = 0.99) -> np.ndarray:
    """Prevent clipping by scaling down only when the peak exceeds ``ceiling``."""
    peak = float(np.max(np.abs(x))) if x.size else 0.0
    if peak <= ceiling:
        return x
    return (x * (ceiling / peak)).astype(np.float32)


def trim_silence(x: np.ndarray, sr: int, threshold_db: float = -48.0, keep_ms: int = 60) -> np.ndarray:
    """Remove leading/trailing silence, keeping a small margin."""
    frame = max(1, int(sr * 0.01))
    n = len(x) // frame
    if n == 0:
        return x
    blocks = x[: n * frame].reshape(n, frame)
    rms = np.sqrt(np.mean(blocks.astype(np.float64) ** 2, axis=1))
    loud = np.where(20.0 * np.log10(rms + EPS) > threshold_db)[0]
    if loud.size == 0:
        return x
    keep = int(sr * keep_ms / 1000)
    start = max(0, int(loud[0]) * frame - keep)
    end = min(len(x), (int(loud[-1]) + 1) * frame + keep)
    return x[start:end]


def fade_edges(x: np.ndarray, sr: int, ms: int = 6) -> np.ndarray:
    """Short fade in/out to avoid clicks when pieces are joined."""
    n = min(int(sr * ms / 1000), len(x) // 2)
    if n <= 1:
        return x
    y = x.copy()
    ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)
    y[:n] *= ramp
    y[-n:] *= ramp[::-1]
    return y


def silence(sr: int, ms: int) -> np.ndarray:
    return np.zeros(max(0, int(sr * ms / 1000)), dtype=np.float32)


def concat_with_pauses(parts: list[np.ndarray], pauses_ms: list[int], sr: int) -> np.ndarray:
    """Join ``parts``; ``pauses_ms[i]`` is the silence inserted *after* part ``i``."""
    if not parts:
        return np.zeros(0, dtype=np.float32)
    pieces: list[np.ndarray] = []
    for i, part in enumerate(parts):
        pieces.append(part)
        if i < len(parts) - 1 and pauses_ms[i] > 0:
            pieces.append(silence(sr, pauses_ms[i]))
    return np.concatenate(pieces).astype(np.float32)


def resample(x: np.ndarray, sr_from: int, sr_to: int) -> np.ndarray:
    """Linear-interpolation resampler (adequate for speech; avoids a SciPy dependency)."""
    if sr_from == sr_to or x.size == 0:
        return x
    new_len = max(1, int(round(len(x) * sr_to / sr_from)))
    positions = np.linspace(0.0, len(x) - 1, new_len)
    return np.interp(positions, np.arange(len(x)), x).astype(np.float32)


# ----------------------------------------------------------------------------- speed
def change_speed(x: np.ndarray, speed: float) -> np.ndarray:
    """Change speaking speed without changing pitch (``speed`` 2.0 = twice as fast)."""
    if abs(speed - 1.0) < 0.01 or x.size < 4096:
        return x
    return _time_stretch(x, 1.0 / max(0.25, float(speed)))[0]


# ----------------------------------------------------------------------------- pitch
def _time_stretch(x: np.ndarray, factor: float, n_fft: int = 2048) -> tuple[np.ndarray, float]:
    """Phase-vocoder time stretch. Returns (audio, effective_factor)."""
    hop_a = n_fft // 4
    hop_s = max(1, int(round(hop_a * factor)))
    effective = hop_s / hop_a
    window = np.hanning(n_fft + 1)[:-1].astype(np.float32)

    padded = np.concatenate([np.zeros(n_fft, np.float32), x.astype(np.float32), np.zeros(n_fft + hop_a, np.float32)])
    n_frames = 1 + (len(padded) - n_fft) // hop_a
    index = np.arange(n_fft)[None, :] + hop_a * np.arange(n_frames)[:, None]
    spectrum = np.fft.rfft(padded[index] * window, axis=1)
    magnitude = np.abs(spectrum)
    phase = np.angle(spectrum)

    omega = 2.0 * np.pi * hop_a * np.arange(spectrum.shape[1]) / n_fft
    delta = np.diff(phase, axis=0) - omega
    delta -= 2.0 * np.pi * np.round(delta / (2.0 * np.pi))
    advance = (omega + delta) * (hop_s / hop_a)
    accumulated = np.vstack([phase[:1], phase[:1] + np.cumsum(advance, axis=0)])

    frames = np.fft.irfft(magnitude * np.exp(1j * accumulated), n=n_fft, axis=1) * window
    out_len = hop_s * (n_frames - 1) + n_fft
    out = np.zeros(out_len, dtype=np.float64)
    norm = np.zeros(out_len, dtype=np.float64)
    win_sq = (window.astype(np.float64)) ** 2
    for t in range(n_frames):
        a = t * hop_s
        out[a : a + n_fft] += frames[t]
        norm[a : a + n_fft] += win_sq
    out /= np.maximum(norm, 1e-3)

    start = int(round(n_fft * effective))
    target = int(round(len(x) * effective))
    out = out[start : start + target]
    if len(out) < target:
        out = np.pad(out, (0, target - len(out)))
    return out.astype(np.float32), effective


def pitch_shift(x: np.ndarray, sr: int, semitones: float) -> np.ndarray:
    """Shift pitch by ``semitones`` while keeping duration (phase vocoder + resample).

    Works well for +/-6 semitones on speech. ``sr`` is unused today but kept so a
    higher-quality implementation can be swapped in without changing callers.
    """
    if abs(semitones) < 0.01 or x.size < 4096:
        return x
    ratio = 2.0 ** (semitones / 12.0)
    stretched, effective = _time_stretch(x, ratio)
    positions = np.linspace(0.0, len(stretched) - 1, len(x))
    return np.interp(positions, np.arange(len(stretched)), stretched).astype(np.float32)
