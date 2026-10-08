"""Custom voice profiles: validate a reference recording, store it locally, and (only when a
real cloning engine is installed) build a reusable speaker model from it.

A profile created without a cloning engine is an honest "reference only" profile: it keeps the
validated recording and its quality report, and can be upgraded later. It cannot speak.
"""

from __future__ import annotations

import re
import shutil
import uuid
from pathlib import Path

from ..audio.export import read_audio, write_wav
from ..audio.validation import ReferenceReport, analyze_reference
from ..config import get_paths
from ..engines.base import SpeakerModel
from ..engines.registry import get_cloning_engine
from ..errors import AudioValidationError, EngineUnavailable
from ..storage import repository as repo


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:32] or "voice"


def analyze_upload(data: bytes) -> ReferenceReport:
    return analyze_reference(data)


def create_profile(*, name: str, language: str | None, data: bytes, notes: str = "") -> int:
    """Validate and store a reference recording as a new profile. Returns the profile id."""
    name = name.strip()
    if not name:
        raise AudioValidationError("Please give this voice a name.")
    report = analyze_reference(data)
    if not report.usable:
        raise AudioValidationError("This recording has problems that must be fixed first. See the report.")

    audio = read_audio(data)
    target = get_paths().references / f"{_slug(name)}-{uuid.uuid4().hex[:8]}.wav"
    write_wav(target, audio)
    profile_id = repo.add_voice_profile(
        name=name,
        language=language,
        reference_path=str(target),
        duration=report.duration,
        quality_score=report.score,
        quality_level=report.level,
        analysis=report.to_dict(),
        notes=notes.strip(),
    )
    engine = get_cloning_engine(language=language)
    if engine.status().available:
        try:
            build_speaker_model(profile_id)
        except Exception:
            pass  # the profile is saved either way; the user can retry from "My voices"
    return profile_id


def build_speaker_model(profile_id: int) -> SpeakerModel:
    """Ask the active cloning engine to build a speaker model. Raises EngineUnavailable if none."""
    profile = repo.get_voice_profile(profile_id)
    if profile is None:
        raise AudioValidationError("This voice profile no longer exists.")
    engine = get_cloning_engine(language=profile.get("language"))
    status = engine.status()
    if not status.available:
        raise EngineUnavailable(status.message)
    output = get_paths().voice_models / f"profile_{profile_id}"
    output.mkdir(parents=True, exist_ok=True)
    model = engine.create_speaker_model(Path(profile["reference_path"]), output, profile.get("language"))
    repo.update_voice_profile(profile_id, engine_id=model.engine_id, model_path=model.model_path, model_ready=1)
    return model


def delete_profile(profile_id: int) -> None:
    profile = repo.get_voice_profile(profile_id)
    repo.delete_voice_profile(profile_id)
    if not profile:
        return
    try:
        Path(profile["reference_path"]).unlink(missing_ok=True)
        shutil.rmtree(get_paths().voice_models / f"profile_{profile_id}", ignore_errors=True)
    except OSError:
        pass


def profile_report(profile: dict) -> ReferenceReport | None:
    import json

    try:
        return ReferenceReport.from_dict(json.loads(profile.get("analysis_json") or "{}"))
    except (TypeError, ValueError):
        return None
