"""Waveform summary used to draw the audio player (pure numpy)."""

from __future__ import annotations

import numpy as np


def compute_peaks(samples: np.ndarray, bars: int = 160) -> list[float]:
    """Reduce ``samples`` to ``bars`` values in [0, 1] (peak per bin, gently compressed)."""
    samples = np.asarray(samples, dtype=np.float32)
    if samples.size == 0 or bars <= 0:
        return [0.0] * max(0, bars)
    bars = int(min(bars, samples.size))
    edges = np.linspace(0, samples.size, bars + 1, dtype=np.int64)
    peaks = np.array(
        [float(np.max(np.abs(samples[a:b]))) if b > a else 0.0 for a, b in zip(edges[:-1], edges[1:])],
        dtype=np.float64,
    )
    top = peaks.max()
    if top <= 1e-9:
        return [0.0] * bars
    return [round(float(v), 3) for v in np.sqrt(peaks / top)]
