"""DSP and reference-audio validation."""

import unittest

import numpy as np

from tests import _env  # noqa: F401
from studio.audio import processing as dsp
from studio.audio.export import read_audio, wav_bytes
from studio.audio.types import AudioData
from studio.audio.validation import analyze_reference

SR = 22050


def _tone(freq: float, seconds: float, amp: float = 0.4) -> np.ndarray:
    t = np.arange(int(SR * seconds)) / SR
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def _dominant_freq(x: np.ndarray) -> float:
    spectrum = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    return float(np.argmax(spectrum) * SR / len(x))


def _speechlike(seconds: float, noise: float = 0.002, amp: float = 0.4, seed: int = 1) -> np.ndarray:
    """Bursts of voiced-like energy with pauses over a low noise floor."""
    rng = np.random.default_rng(seed)
    n = int(SR * seconds)
    t = np.arange(n) / SR
    envelope = (np.sin(2 * np.pi * 1.5 * t) > -0.3).astype(np.float32)
    signal = amp * envelope * (np.sin(2 * np.pi * 180 * t) + 0.5 * np.sin(2 * np.pi * 540 * t)) / 1.5
    return (signal + noise * rng.standard_normal(n)).astype(np.float32)


class ProcessingTests(unittest.TestCase):
    def test_pitch_shift_octave_up_and_down_keeps_length(self):
        base = _tone(220, 2.0)
        up = dsp.pitch_shift(base, SR, 12)
        down = dsp.pitch_shift(base, SR, -12)
        self.assertEqual(len(up), len(base))
        self.assertAlmostEqual(_dominant_freq(up), 440, delta=8)
        self.assertAlmostEqual(_dominant_freq(down), 110, delta=8)

    def test_pitch_zero_is_identity(self):
        base = _tone(220, 1.0)
        self.assertTrue(np.array_equal(dsp.pitch_shift(base, SR, 0.0), base))

    def test_trim_silence(self):
        x = np.concatenate([np.zeros(SR), _tone(300, 1.0), np.zeros(SR)])
        trimmed = dsp.trim_silence(x, SR)
        self.assertLess(len(trimmed), len(x) * 0.6)
        self.assertGreater(len(trimmed), SR)

    def test_normalize_and_gain(self):
        x = _tone(300, 0.5, amp=0.1)
        y = dsp.peak_normalize(x, -1.0)
        self.assertAlmostEqual(dsp.peak_dbfs(y), -1.0, delta=0.05)
        z = dsp.apply_gain_db(y, -6.0)
        self.assertAlmostEqual(dsp.peak_dbfs(z), -7.0, delta=0.05)

    def test_guard_peaks(self):
        guarded = dsp.guard_peaks(np.array([1.8, -0.5], np.float32))
        self.assertAlmostEqual(float(np.max(np.abs(guarded))), 0.99, places=5)

    def test_concat_with_pauses(self):
        a, b = _tone(300, 0.5), _tone(300, 0.5)
        out = dsp.concat_with_pauses([a, b], [500], SR)
        self.assertEqual(len(out), len(a) + len(b) + int(SR * 0.5))

    def test_wav_roundtrip(self):
        audio = AudioData(_tone(300, 0.5), SR)
        back = read_audio(wav_bytes(audio))
        self.assertEqual(back.sample_rate, SR)
        self.assertEqual(len(back.samples), len(audio.samples))
        self.assertLess(float(np.max(np.abs(back.samples - audio.samples))), 1e-3)


class ValidationTests(unittest.TestCase):
    def test_clean_recording_is_usable_and_scores_well(self):
        report = analyze_reference(wav_bytes(AudioData(_speechlike(25), SR)))
        self.assertTrue(report.usable)
        self.assertGreaterEqual(report.score, 75)
        self.assertEqual(report.channels, 1)

    def test_too_short_is_rejected(self):
        report = analyze_reference(wav_bytes(AudioData(_speechlike(1.5), SR)))
        self.assertFalse(report.usable)
        self.assertTrue(any("short" in i.message.lower() for i in report.issues))

    def test_clipped_recording_is_flagged(self):
        loud = np.clip(_speechlike(20, amp=3.0), -1, 1)
        report = analyze_reference(wav_bytes(AudioData(loud, SR)))
        self.assertGreater(report.clipping_pct, 2.0)
        self.assertFalse(report.usable)

    def test_noisy_recording_scores_lower(self):
        clean = analyze_reference(wav_bytes(AudioData(_speechlike(20), SR)))
        noisy = analyze_reference(wav_bytes(AudioData(_speechlike(20, noise=0.12), SR)))
        self.assertLess(noisy.score, clean.score)

    def test_silence_is_rejected(self):
        report = analyze_reference(wav_bytes(AudioData(np.zeros(SR * 12, np.float32), SR)))
        self.assertFalse(report.usable)

    def test_report_serialisation(self):
        report = analyze_reference(wav_bytes(AudioData(_speechlike(20), SR)))
        from studio.audio.validation import ReferenceReport

        self.assertEqual(ReferenceReport.from_dict(report.to_dict()).score, report.score)


if __name__ == "__main__":
    unittest.main()
