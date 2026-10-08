"""Objective quality checks for voice-cloning reference recordings.

Everything here is a real measurement of the supplied audio (levels, clipping, noise floor,
estimated SNR, duration). It makes no claims about how well any particular cloning model
will perform - it only flags problems that are known to hurt reference-based voice cloning.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import BinaryIO

import numpy as np

from .export import read_audio_multichannel
from .processing import EPS


@dataclass
class Issue:
    severity: str  # "error" | "warning" | "info"
    message: str


@dataclass
class ReferenceReport:
    duration: float
    sample_rate: int
    channels: int
    peak_dbfs: float
    rms_dbfs: float
    clipping_pct: float
    noise_floor_dbfs: float
    snr_db: float
    speech_ratio: float
    score: int
    level: str  # excellent | good | fair | poor
    usable: bool
    issues: list[Issue] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ReferenceReport":
        data = dict(data)
        data["issues"] = [Issue(**i) for i in data.get("issues", [])]
        return cls(**data)


def _level(score: int) -> str:
    if score >= 85:
        return "excellent"
    if score >= 70:
        return "good"
    if score >= 50:
        return "fair"
    return "poor"


def analyze_reference(source: bytes | str | Path | BinaryIO) -> ReferenceReport:
    """Analyse a reference recording and return a scored report."""
    data, rate = read_audio_multichannel(source)
    channels = data.shape[1]
    mono = data.mean(axis=1)
    duration = len(mono) / float(rate) if rate else 0.0

    abs_mono = np.abs(mono)
    peak = float(abs_mono.max()) if mono.size else 0.0
    rms = float(np.sqrt(np.mean(mono.astype(np.float64) ** 2))) if mono.size else 0.0
    peak_db = 20.0 * np.log10(max(peak, EPS))
    rms_db = 20.0 * np.log10(max(rms, EPS))
    clipping_pct = float(np.mean(abs_mono >= 0.999) * 100.0) if mono.size else 0.0

    frame = max(1, int(rate * 0.03))
    n = len(mono) // frame
    if n >= 4:
        blocks = mono[: n * frame].reshape(n, frame).astype(np.float64)
        frame_db = 20.0 * np.log10(np.sqrt(np.mean(blocks**2, axis=1)) + EPS)
        noise_db = float(np.percentile(frame_db, 10))
        speech_db = float(np.percentile(frame_db, 90))
        snr = speech_db - noise_db
        speech_ratio = float(np.mean((frame_db > noise_db + 10.0) & (frame_db > -50.0)))
    else:
        noise_db, snr, speech_ratio = -120.0, 0.0, 0.0

    issues: list[Issue] = []
    score = 100

    if duration < 3.0:
        issues.append(Issue("error", f"Too short ({duration:.1f}s). Record at least 10 seconds of continuous speech."))
        score -= 60
    elif duration < 8.0:
        issues.append(Issue("warning", f"Short recording ({duration:.1f}s). 15-60 seconds usually works best."))
        score -= 25
    elif duration < 15.0:
        issues.append(Issue("info", f"{duration:.0f}s is usable; 15-60 seconds gives cloning models more to work with."))
        score -= 6
    elif duration > 180.0:
        issues.append(Issue("info", "Very long recording. Most models only need 30-60 seconds; consider trimming."))

    if rate < 16000:
        issues.append(Issue("warning", f"Low sample rate ({rate} Hz). Use 22.05 kHz or higher if possible."))
        score -= 15

    if clipping_pct > 2.0:
        issues.append(Issue("error", f"Heavy clipping ({clipping_pct:.1f}% of samples). Re-record with lower input gain."))
        score -= 35
    elif clipping_pct > 0.2:
        issues.append(Issue("warning", f"Some clipping ({clipping_pct:.2f}% of samples). Lower the input gain."))
        score -= 15

    if rms_db < -45.0:
        issues.append(Issue("error", "The recording is almost silent. Check the microphone and input level."))
        score -= 45
    elif rms_db < -32.0:
        issues.append(Issue("warning", f"Quiet recording (average {rms_db:.0f} dBFS). Move closer or raise the input level."))
        score -= 10

    if n >= 4:
        if snr < 6.0:
            issues.append(Issue("error", f"Very noisy (estimated SNR {snr:.0f} dB). Record in a quieter room."))
            score -= 40
        elif snr < 15.0:
            issues.append(Issue("warning", f"Background noise is noticeable (estimated SNR {snr:.0f} dB)."))
            score -= 22
        elif snr < 22.0:
            issues.append(Issue("info", f"Moderate background noise (estimated SNR {snr:.0f} dB)."))
            score -= 6
        if speech_ratio < 0.35:
            issues.append(Issue("warning", "Much of the recording is silence or pauses. Trim it or speak continuously."))
            score -= 15

    if channels > 1:
        issues.append(Issue("info", f"{channels} channels detected; the reference will be mixed down to mono."))

    score = int(max(0, min(100, score)))
    usable = not any(i.severity == "error" for i in issues)
    if usable and not issues:
        issues.append(Issue("info", "No problems found. This is a clean reference recording."))

    return ReferenceReport(
        duration=round(duration, 2),
        sample_rate=int(rate),
        channels=int(channels),
        peak_dbfs=round(peak_db, 1),
        rms_dbfs=round(rms_db, 1),
        clipping_pct=round(clipping_pct, 3),
        noise_floor_dbfs=round(noise_db, 1),
        snr_db=round(snr, 1),
        speech_ratio=round(speech_ratio, 2),
        score=score,
        level=_level(score),
        usable=usable,
        issues=issues,
    )
