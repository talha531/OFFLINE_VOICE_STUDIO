# Adding a real offline voice-cloning engine

Piper cannot clone voices. The app ships a real, optional backend - **Coqui XTTS-v2**
(`studio/engines/plugins/xtts_engine.py`, see README "Voice cloning setup") - and falls back to a
`NullCloningEngine` that reports "No voice-cloning engine is installed" and refuses to synthesise
when it is not installed. This guide shows how to add *another* backend; `xtts_engine.py` is a
working reference implementation.

## The contract (`studio/engines/base.py`)

```python
class CloningEngine(ABC):
    id: str            # unique; stored on each voice profile
    name: str          # shown in the UI
    def status(self) -> EngineStatus: ...                      # honest readiness (package AND weights present)
    def supported_languages(self) -> list[str]: ...            # ["en", "es"]
    def create_speaker_model(self, reference_wav, output_dir, language) -> SpeakerModel: ...
    def synthesize(self, text, model: SpeakerModel, options: SynthesisOptions) -> AudioData: ...
```

* `create_speaker_model` receives the validated reference WAV, writes whatever the model needs
  (embedding, conditioning latents, a copy of the reference) into `output_dir`, and returns
  `SpeakerModel(engine_id, model_path, info)`. This runs once per profile.
* `synthesize` loads that artifact and returns `AudioData(samples_float32_mono, sample_rate)`.
  Speed, pitch and volume are available in `options` (the pipeline also post-processes audio).
* Raise `EngineUnavailable` / `EngineError` (from `studio.errors`) with a human-readable message;
  the UI shows it as an error state.

## Steps

1. Copy `studio/engines/plugins/_template.py` to `studio/engines/plugins/my_engine.py`.
2. Implement the four methods against a model that runs **fully offline** (weights on disk).
3. Keep `ENGINE = MyEngine` at the bottom of the file.
4. Install the model's Python package into `.venv`, restart the app.

The registry (`studio/engines/registry.py`) discovers every non-underscore module in `plugins/`.
A plugin that fails to import is skipped and listed under Settings -> System checks (and Custom Voice); it can never
break the app. `get_cloning_engine()` picks the first plugin whose `status().available` is true.

## Checklist before you trust it

* `status()` must be False when weights are missing - never claim readiness you cannot deliver.
* No network calls at synthesis time.
* Test with a 10-30 s clean reference and confirm the output is audibly the reference speaker.
* Only clone voices you have the right to use.