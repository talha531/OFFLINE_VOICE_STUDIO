import unittest

import numpy as np

from tests import _env  # noqa: F401
from studio.audio.waveform import compute_peaks
from studio.services import health


class WaveformTests(unittest.TestCase):
    def test_peaks_length_and_range(self):
        peaks = compute_peaks(np.sin(np.linspace(0, 80, 20000)), 64)
        self.assertEqual(len(peaks), 64)
        self.assertTrue(all(0.0 <= p <= 1.0 for p in peaks))
        self.assertAlmostEqual(max(peaks), 1.0, places=2)

    def test_silence_and_empty(self):
        self.assertEqual(set(compute_peaks(np.zeros(1000), 10)), {0.0})
        self.assertEqual(compute_peaks(np.zeros(0), 5), [0.0] * 5)

    def test_short_input_gives_fewer_bars(self):
        self.assertEqual(len(compute_peaks(np.ones(3), 160)), 3)


class HealthTests(unittest.TestCase):
    def test_checks_have_ids_and_honest_cloning_status(self):
        checks = {c.id: c for c in health.run_checks()}
        self.assertIn("piper", checks)
        self.assertIn("cloning", checks)
        self.assertFalse(checks["cloning"].ok)  # no real cloning engine is bundled
        self.assertFalse(checks["cloning"].required)


if __name__ == "__main__":
    unittest.main()


class MaintenanceTests(unittest.TestCase):
    def test_storage_summary_and_cleanup(self):
        from studio.config import get_paths
        from studio.services import maintenance

        paths = get_paths()
        (paths.temp / "scratch.bin").write_bytes(b"x" * 2048)
        summary = maintenance.storage_summary()
        self.assertGreaterEqual(summary.temp, 2048)
        freed = maintenance.clear_temp_files()
        self.assertGreaterEqual(freed, 2048)
        self.assertEqual(maintenance.storage_summary().temp, 0)

    def test_delete_all_audio_removes_files_and_rows(self):
        from studio.config import get_paths
        from studio.services import maintenance
        from studio.storage import repository as repo
        from studio.storage.db import ensure_ready

        ensure_ready()
        path = get_paths().audio / "m1.wav"
        path.write_bytes(b"RIFF")
        repo.add_audio(title="m", path=str(path), fmt="wav", duration=1, size_bytes=4, voice_label="v", language="en", text_preview="t", history_id=None)
        self.assertGreaterEqual(maintenance.delete_all_audio(), 1)
        self.assertFalse(path.exists())
        self.assertEqual(repo.list_audio(), [])
