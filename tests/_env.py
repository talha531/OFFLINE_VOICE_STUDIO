"""Test bootstrap: isolate all data in a temp folder *before* the studio package is imported."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_TMP = tempfile.mkdtemp(prefix="voice_studio_test_")
os.environ["VOICE_STUDIO_HOME"] = os.path.join(_TMP, "data")
os.environ["VOICE_STUDIO_MODELS"] = os.path.join(_TMP, "models")
TMP = Path(_TMP)
