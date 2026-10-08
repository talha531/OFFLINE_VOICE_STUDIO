"""The single audio container passed between engines, processing and export."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class AudioData:
    """Mono floating point audio in the range [-1, 1]."""

    samples: np.ndarray
    sample_rate: int

    def __post_init__(self) -> None:
        samples = np.asarray(self.samples, dtype=np.float32)
        if samples.ndim > 1:
            samples = samples.mean(axis=1)
        self.samples = samples
        self.sample_rate = int(self.sample_rate)

    @property
    def duration(self) -> float:
        return float(len(self.samples)) / float(self.sample_rate) if self.sample_rate else 0.0

    @property
    def is_empty(self) -> bool:
        return self.samples.size == 0
