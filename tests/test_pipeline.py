"""End-to-end generation with a test-only engine (a tone generator, never shipped in the app),
plus job control, storage and the honest 'no cloning engine' behaviour."""

import json
import threading
import time
import unittest
from pathlib import Path

import numpy as np

from tests import _env  # noqa: F401
from studio.audio.export import read_audio, wav_bytes
from studio.audio.types import AudioData
from studio.config import get_paths
from studio.engines import registry
from studio.engines.base import EngineStatus, SynthesisOptions, TTSEngine, VoiceInfo
from studio.engines.piper_engine import PiperEngine
from studio.errors import EngineUnavailable, JobCancelled
from studio.services import jobs, pipeline, voice_profiles
from studio.services.pipeline import GenerationRequest
from studio.storage import repository as repo
from studio.storage.db import ensure_ready

SR = 22050
VOICE = VoiceInfo("test-voice", "Test", "en_US", "English (United States)", "female", "medium", SR, "test", "x.onnx")


class ToneEngine(TTSEngine):
    """TEST DOUBLE: 40 ms of tone per character, so durations are predictable."""

    id = "test-tone"
    name = "Test tone"

    def __init__(self, delay: float = 0.0):
        self.delay = delay
        self.calls = 0

    def status(self):
        return EngineStatus(True, "ok")

    def list_voices(self):
        return [VOICE]

    def synthesize(self, text, voice, options: SynthesisOptions):
        self.calls += 1
        if self.delay:
            time.sleep(self.delay)
        n = int(SR * 0.04 * len(text) / options.speed)
        t = np.arange(n) / SR
        return AudioData((0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32), SR)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        ensure_ready()
        self.engine = ToneEngine()
        registry.set_tts_engine(self.engine)

    def tearDown(self):
        registry.set_tts_engine(None)

    def _request(self, **kw):
        base = dict(text="Hello there. " * 40, voice_id="test-voice", max_chars=120, formats=("wav",), pause_ms=100)
        base.update(kw)
        return GenerationRequest(**base)

    def test_full_generation_records_library_and_history(self):
        progress = []
        result = pipeline.run_generation(self._request(), None, lambda d, t, m: progress.append((d, t)))
        self.assertGreater(result.chunk_count, 3)
        self.assertEqual(progress[0][1], result.chunk_count)
        self.assertEqual(progress[-1][0], result.chunk_count)
        wav = result.files[0]
        self.assertTrue(wav.path.exists())
        audio = read_audio(wav.path.read_bytes())
        self.assertAlmostEqual(audio.duration, result.duration, delta=0.05)
        self.assertLessEqual(float(np.max(np.abs(audio.samples))), 1.0)

        item = repo.get_audio(wav.audio_id)
        self.assertEqual(item["format"], "wav")
        history = repo.get_history(result.history_id)
        self.assertEqual(history["status"], "done")
        self.assertEqual(json.loads(history["params_json"])["speed"], 1.0)

    def test_speed_changes_duration_and_volume_changes_level(self):
        normal = pipeline.render_preview(self._request(text="Hello there my friend.", normalize=False))
        fast = pipeline.render_preview(self._request(text="Hello there my friend.", speed=2.0, normalize=False))
        self.assertLess(fast.duration, normal.duration * 0.7)
        quiet = pipeline.render_preview(self._request(text="Hello there my friend.", normalize=False, volume_db=-12))
        self.assertLess(np.max(np.abs(quiet.samples)), np.max(np.abs(normal.samples)) * 0.4)

    def test_pitch_is_applied(self):
        audio = pipeline.render_preview(self._request(text="Hello there my friend, how are you today.", pitch=12, normalize=False))
        spectrum = np.abs(np.fft.rfft(audio.samples * np.hanning(len(audio.samples))))
        peak = np.argmax(spectrum) * audio.sample_rate / len(audio.samples)
        self.assertAlmostEqual(peak, 440, delta=15)

    def test_cancellation_records_history_and_raises(self):
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(JobCancelled):
            pipeline.run_generation(self._request(), cancel)
        self.assertEqual(repo.list_history(status="cancelled", limit=1)[0]["status"], "cancelled")

    def test_job_manager_progress_cancel_and_finish(self):
        self.engine.delay = 0.05
        manager = jobs.JobManager()
        job = manager.submit(self._request())
        deadline = time.time() + 10
        while time.time() < deadline and job.snapshot().completed < 2:
            time.sleep(0.02)
        manager.cancel(job.id)
        while time.time() < deadline and not job.snapshot().finished:
            time.sleep(0.02)
        self.assertEqual(job.snapshot().state, jobs.JobState.CANCELLED)

        self.engine.delay = 0.0
        job2 = manager.submit(self._request(text="Short text."))
        while time.time() < deadline and not job2.snapshot().finished:
            time.sleep(0.02)
        snap = job2.snapshot()
        self.assertEqual(snap.state, jobs.JobState.DONE)
        self.assertIsNotNone(snap.result)

    def test_failure_is_reported_not_raised_in_job(self):
        manager = jobs.JobManager()
        job = manager.submit(self._request(voice_id="missing-voice"))
        deadline = time.time() + 5
        while time.time() < deadline and not job.snapshot().finished:
            time.sleep(0.02)
        snap = job.snapshot()
        self.assertEqual(snap.state, jobs.JobState.FAILED)
        self.assertIn("not installed", snap.error)

    def test_empty_text_rejected(self):
        with self.assertRaises(Exception):
            pipeline.run_generation(self._request(text="   "))

    def test_custom_voice_without_engine_is_honest(self):
        t = np.arange(SR * 20) / SR
        bursts = (np.sin(2 * np.pi * 1.5 * t) > -0.3) * 0.4 * np.sin(2 * np.pi * 180 * t)
        noise = 0.002 * np.random.default_rng(3).standard_normal(len(t))
        data = wav_bytes(AudioData((bursts + noise).astype(np.float32), SR))
        pid = voice_profiles.create_profile(name="Me", language="en", data=data)
        profile = repo.get_voice_profile(pid)
        self.assertEqual(profile["model_ready"], 0)
        self.assertTrue(Path(profile["reference_path"]).exists())
        with self.assertRaises(EngineUnavailable):
            pipeline.render_preview(self._request(mode="custom", profile_id=pid))
        with self.assertRaises(EngineUnavailable):
            voice_profiles.build_speaker_model(pid)
        voice_profiles.delete_profile(pid)
        self.assertIsNone(repo.get_voice_profile(pid))
        self.assertFalse(Path(profile["reference_path"]).exists())


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        ensure_ready()

    def test_settings_roundtrip_and_reset(self):
        repo.save_settings({"pause_ms": 400, "unknown_key": 1})
        s = repo.get_settings()
        self.assertEqual(s["pause_ms"], 400)
        self.assertNotIn("unknown_key", s)
        repo.reset_settings()
        self.assertEqual(repo.get_settings()["pause_ms"], 250)

    def test_documents_crud(self):
        did = repo.add_document("a.txt", "txt", "hello")
        self.assertEqual(repo.get_document(did)["text"], "hello")
        repo.update_document(did, "hello world")
        self.assertEqual(repo.get_document(did)["char_count"], 11)
        repo.delete_document(did)
        self.assertIsNone(repo.get_document(did))

    def test_library_search_favorite_delete(self):
        path = get_paths().audio / "t.wav"
        path.write_bytes(b"RIFF")
        aid = repo.add_audio(title="Findable title", path=str(path), fmt="wav", duration=1.0, size_bytes=4,
                             voice_label="V", language="en", text_preview="abc", history_id=None)
        self.assertEqual(len(repo.list_audio(search="findable")), 1)
        repo.set_favorite(aid, True)
        self.assertEqual(len(repo.list_audio(favorites_only=True)), 1)
        repo.delete_audio(aid)
        self.assertFalse(path.exists())
        self.assertIsNone(repo.get_audio(aid))


class PiperDiscoveryTests(unittest.TestCase):
    def test_voice_discovery_reads_metadata_and_gender(self):
        folder = _env.TMP / "piper_models"
        folder.mkdir(exist_ok=True)
        (folder / "en_GB-alan-medium.onnx").write_bytes(b"x")
        (folder / "en_GB-alan-medium.onnx.json").write_text(json.dumps({
            "audio": {"sample_rate": 22050, "quality": "medium"},
            "language": {"code": "en_GB", "name_english": "English", "country_english": "Great Britain"},
            "num_speakers": 1,
        }))
        (folder / "en_GB-alan-medium.studio.json").write_text(json.dumps({"gender": "male"}))
        (folder / "orphan-low.onnx").write_bytes(b"x")  # no .json: must be ignored
        voices = PiperEngine(folder).list_voices()
        self.assertEqual(len(voices), 1)
        v = voices[0]
        self.assertEqual((v.id, v.name, v.gender, v.language_family), ("en_GB-alan-medium", "Alan", "male", "en"))
        self.assertEqual(v.language_name, "English (Great Britain)")

    def test_status_when_empty(self):
        status = PiperEngine(_env.TMP / "empty_models").status()
        self.assertFalse(status.available)
        self.assertTrue(status.hints)




class CompositeAndMmsTests(unittest.TestCase):
    def _fake_mms_folder(self, root, codes):
        import json as _json

        for code in codes:
            d = root / code
            d.mkdir(parents=True)
            (d / "config.json").write_text(_json.dumps({"sampling_rate": 16000}))
            (d / "vocab.json").write_text("{}")
            (d / "model.safetensors").write_bytes(b"x")

    def test_mms_discovers_language_folders(self):
        from studio.engines.mms_engine import MmsEngine

        root = _env.TMP / "mms_models"
        self._fake_mms_folder(root, ["urd-script_arabic", "hin", "xyz"])
        (root / "incomplete").mkdir()
        voices = MmsEngine(root).list_voices()
        by_name = {v.language_name: v for v in voices}
        self.assertEqual(by_name["Urdu"].language_code, "ur")
        self.assertEqual(by_name["Hindi"].language_code, "hi")
        self.assertIn("XYZ", by_name)
        self.assertEqual(len(voices), 3)

    def test_mms_without_models_is_unavailable_with_hints(self):
        from studio.engines.mms_engine import MmsEngine

        status = MmsEngine(_env.TMP / "no_mms").status()
        self.assertFalse(status.available)
        self.assertTrue(status.hints)

    def test_composite_merges_voices_and_routes_synthesis(self):
        import numpy as np

        from studio.audio.types import AudioData
        from studio.engines.base import EngineStatus, SynthesisOptions, TTSEngine, VoiceInfo
        from studio.engines.composite import CompositeTTSEngine

        def make(engine_id, lang_code, lang_name, ok=True):
            class Fake(TTSEngine):
                id = engine_id
                name = engine_id

                def status(self):
                    return EngineStatus(ok, "ready" if ok else "missing", ("hint",))

                def list_voices(self):
                    return [VoiceInfo("v-" + engine_id, "V", lang_code, lang_name, "unspecified", "q", 16000, engine_id, "")]

                def synthesize(self, text, voice, options):
                    return AudioData(np.full(10, 0.1 if engine_id == "a" else 0.2, dtype=np.float32), 16000)

            return Fake()

        a, b, down = make("a", "en_US", "English"), make("b", "ur", "Urdu"), make("c", "xx", "Nowhere", ok=False)
        comp = CompositeTTSEngine([a, b, down])
        voices = comp.list_voices()
        self.assertEqual({v.language_name for v in voices}, {"English", "Urdu"})  # unavailable engine hidden
        self.assertTrue(comp.status().available)
        urdu = next(v for v in voices if v.engine_id == "b")
        out = comp.synthesize("x", urdu, SynthesisOptions())
        self.assertAlmostEqual(float(out.samples[0]), 0.2, places=5)
        none_ready = CompositeTTSEngine([down])
        self.assertFalse(none_ready.status().available)
        self.assertEqual(none_ready.list_voices(), [])


class _FakeTensor:  # module level so pickle can store it
    def __init__(self, v=1.0):
        self.v = v

    def detach(self):
        return self

    def cpu(self):
        return self

    def to(self, _):
        return self


class XttsPluginTests(unittest.TestCase):
    """Exercises the XTTS plugin's own logic with stand-in torch/TTS modules (no real model)."""

    def _install_fakes(self):
        import pickle
        import sys
        import types

        import numpy as np

        T = _FakeTensor

        torch = types.ModuleType("torch")
        torch.cuda = types.SimpleNamespace(is_available=lambda: False)
        torch.save = lambda obj, path: open(path, "wb").write(pickle.dumps(obj))
        torch.load = lambda path, **k: pickle.loads(open(path, "rb").read())
        seen = {}

        class FakeXtts:
            @classmethod
            def init_from_config(cls, cfg):
                return cls()

            def load_checkpoint(self, cfg, checkpoint_dir=None, eval=True):
                seen["dir"] = checkpoint_dir

            def to(self, _):
                return self

            def get_conditioning_latents(self, audio_path):
                seen["ref"] = audio_path
                return T(), T()

            def inference(self, text, language, gpt_cond_latent, speaker_embedding, speed, enable_text_splitting):
                seen["call"] = (text, language, speed)
                return {"wav": np.full(2400, 0.25, dtype=np.float32)}

        class FakeCfg:
            def load_json(self, path):
                seen["cfg"] = path

        mods = {
            "torch": torch,
            "TTS": types.ModuleType("TTS"),
            "TTS.tts": types.ModuleType("TTS.tts"),
            "TTS.tts.configs": types.ModuleType("TTS.tts.configs"),
            "TTS.tts.configs.xtts_config": types.SimpleNamespace(XttsConfig=FakeCfg),
            "TTS.tts.models": types.ModuleType("TTS.tts.models"),
            "TTS.tts.models.xtts": types.SimpleNamespace(Xtts=FakeXtts),
        }
        for name, mod in mods.items():
            sys.modules[name] = mod
        self.addCleanup(lambda: [sys.modules.pop(n, None) for n in mods])
        return seen

    def _engine(self, with_files=True):
        from studio.engines.plugins.xtts_engine import XttsEngine

        folder = _env.TMP / ("xtts_full" if with_files else "xtts_empty")
        folder.mkdir(exist_ok=True)
        if with_files:
            for f in ("config.json", "model.pth", "vocab.json"):
                (folder / f).write_bytes(b"{}")
        return XttsEngine(folder)

    def test_status_reports_missing_pieces_honestly(self):
        engine = self._engine(with_files=False)
        status = engine.status()
        self.assertFalse(status.available)
        self.assertTrue(status.hints)

    def test_plugin_is_discovered_by_registry(self):
        from studio.engines.registry import list_cloning_engines

        self.assertIn("xtts-v2", [e.id for e in list_cloning_engines()])

    def test_clone_then_speak(self):
        from studio.engines.base import SynthesisOptions

        seen = self._install_fakes()
        engine = self._engine()
        out_dir = _env.TMP / "xtts_profile"
        ref = _env.TMP / "ref.wav"
        ref.write_bytes(b"RIFF")
        model = engine.create_speaker_model(ref, out_dir, "hi")
        self.assertTrue((out_dir / "speaker.pt").exists())
        self.assertEqual(seen["ref"], [str(ref)])
        audio = engine.synthesize("नमस्ते", model, SynthesisOptions(speed=1.2, language="hi"))
        self.assertEqual(audio.sample_rate, 24000)
        self.assertEqual(len(audio.samples), 2400)
        self.assertEqual(seen["call"], ("नमस्ते", "hi", 1.2))

    def test_unsupported_language_gives_clear_error(self):
        from studio.engines.base import SpeakerModel, SynthesisOptions
        from studio.errors import EngineError

        self._install_fakes()
        engine = self._engine()
        with self.assertRaises(EngineError) as ctx:
            engine.synthesize("x", SpeakerModel("xtts-v2", "nowhere.pt"), SynthesisOptions(language="ur"))
        self.assertIn("cannot speak Urdu", str(ctx.exception))


class _FakeConds:
    def to(self, _):
        return self

    def save(self, path):
        import pickle

        open(path, "wb").write(pickle.dumps("conds"))


class ChatterboxPluginAndSelectionTests(unittest.TestCase):
    def _fakes(self):
        import sys
        import types

        import numpy as np

        seen = {}

        class FakeModel:
            sr = 24000
            conds = None

            @classmethod
            def from_local(cls, path, device):
                seen["loaded"] = (path, device)
                return cls()

            def prepare_conditionals(self, wav, exaggeration=0.5):
                seen["ref"] = wav
                self.conds = _FakeConds()

            def generate(self, text, language_id):
                seen["gen"] = (text, language_id)
                return np.full((1, 4800), 0.3, dtype=np.float32)

        class FakeConditionals:
            @staticmethod
            def load(path, map_location=None):
                return _FakeConds()

        torch = types.ModuleType("torch")
        torch.cuda = types.SimpleNamespace(is_available=lambda: False)
        cb = types.ModuleType("chatterbox")
        mtl = types.SimpleNamespace(ChatterboxMultilingualTTS=FakeModel, Conditionals=FakeConditionals)
        mods = {"torch": torch, "chatterbox": cb, "chatterbox.mtl_tts": mtl}
        for n, m in mods.items():
            sys.modules[n] = m
        self.addCleanup(lambda: [sys.modules.pop(n, None) for n in mods])
        return seen

    def _engine(self):
        from studio.engines.plugins.chatterbox_engine import ChatterboxEngine

        folder = _env.TMP / "cb_models"
        folder.mkdir(exist_ok=True)
        for f in ("ve.pt", "s3gen.pt", "t3_mtl23ls_v2.safetensors", "grapheme_mtl_merged_expanded_v1.json"):
            (folder / f).write_bytes(b"x")
        return ChatterboxEngine(folder)

    def test_clone_and_speak_hebrew(self):
        from studio.engines.base import SynthesisOptions

        seen = self._fakes()
        engine = self._engine()
        self.assertTrue(engine.status().available)
        ref = _env.TMP / "cb_ref.wav"
        ref.write_bytes(b"RIFF")
        model = engine.create_speaker_model(ref, _env.TMP / "cb_profile", "he")
        audio = engine.synthesize("שלום", model, SynthesisOptions(language="he"))
        self.assertEqual(seen["gen"], ("שלום", "he"))
        self.assertEqual(audio.sample_rate, 24000)
        self.assertEqual(len(audio.samples), 4800)

    def test_unsupported_language_and_missing_files(self):
        from studio.engines.base import SpeakerModel, SynthesisOptions
        from studio.engines.plugins.chatterbox_engine import ChatterboxEngine
        from studio.errors import EngineError

        self._fakes()
        with self.assertRaises(EngineError) as ctx:
            self._engine().synthesize("x", SpeakerModel("chatterbox-mtl", "p.pt"), SynthesisOptions(language="ur"))
        self.assertIn("cannot speak Urdu", str(ctx.exception))
        self.assertFalse(ChatterboxEngine(_env.TMP / "cb_none").status().available)

    def test_registry_prefers_engine_supporting_the_language(self):
        from studio.engines import registry

        class Fake:
            def __init__(self, engine_id, langs):
                self.id, self._langs = engine_id, langs

            def status(self):
                from studio.engines.base import EngineStatus

                return EngineStatus(True, "ok")

            def supported_languages(self):
                return self._langs

        old = registry._cloning
        registry._cloning = {"a": Fake("a", ["en"]), "b": Fake("b", ["he", "cs"])}
        try:
            self.assertEqual(registry.get_cloning_engine(language="he").id, "b")
            self.assertEqual(registry.get_cloning_engine(language="en_US").id, "a")
            self.assertEqual(registry.get_cloning_engine(language="ur").id, "a")  # no match -> any available
            self.assertEqual(registry.cloning_languages(), {"en", "he", "cs"})
        finally:
            registry._cloning = old

    def test_change_speed_alters_length_only_when_needed(self):
        import numpy as np

        from studio.audio.processing import change_speed

        x = (np.sin(np.linspace(0, 400, 24000)) * 0.3).astype(np.float32)
        self.assertEqual(len(change_speed(x, 1.0)), len(x))
        self.assertLess(len(change_speed(x, 2.0)), len(x) * 0.6)
        self.assertGreater(len(change_speed(x, 0.5)), len(x) * 1.6)


if __name__ == "__main__":
    unittest.main()
