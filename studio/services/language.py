"""Best-effort offline language detection (uses ``langdetect`` when installed)."""

from __future__ import annotations

import re

from ..config import LANGUAGE_FAMILIES

_SCRIPTS = (
    ("ar", re.compile(r"[\u0600-\u06FF]")),  # Arabic script; refined to Urdu/Persian below
    ("ru", re.compile(r"[\u0400-\u04FF]")),
    ("hi", re.compile(r"[\u0900-\u097F]")),
    ("bn", re.compile(r"[\u0980-\u09FF]")),
    ("pa", re.compile(r"[\u0A00-\u0A7F]")),
    ("gu", re.compile(r"[\u0A80-\u0AFF]")),
    ("ta", re.compile(r"[\u0B80-\u0BFF]")),
    ("te", re.compile(r"[\u0C00-\u0C7F]")),
    ("kn", re.compile(r"[\u0C80-\u0CFF]")),
    ("ml", re.compile(r"[\u0D00-\u0D7F]")),
    ("th", re.compile(r"[\u0E00-\u0E7F]")),
    ("el", re.compile(r"[\u0370-\u03FF]")),
    ("he", re.compile(r"[\u0590-\u05FF]")),
    ("zh", re.compile(r"[\u4E00-\u9FFF]")),
    ("ja", re.compile(r"[\u3040-\u30FF]")),
    ("ko", re.compile(r"[\uAC00-\uD7AF]")),
)

# Letters that appear in Urdu but not in Arabic (retroflex and aspirated forms, ye barree, ...).
_URDU_ONLY = re.compile("[\u0679\u0688\u0691\u06BA\u06BE\u06C1\u06D2\u06C3]")
# Letters Persian uses that Arabic does not (and Urdu lacks the Urdu-only set above).
_PERSIAN_HINT = re.compile("[\u067E\u0686\u0698\u06AF\u06A9\u06CC]")


def _refine_arabic_script(sample: str) -> str:
    """Arabic-script text may be Arabic, Urdu or Persian; tell them apart by distinctive letters."""
    if len(_URDU_ONLY.findall(sample)) >= 2:
        return "ur"
    if len(_PERSIAN_HINT.findall(sample)) >= 3 and not _URDU_ONLY.search(sample):
        return "fa"
    return "ar"


def language_name(family: str | None) -> str:
    if not family:
        return "Unknown"
    return LANGUAGE_FAMILIES.get(family, family.upper())


def detect_language(text: str) -> str | None:
    """Return a language-family code such as ``"en"``, or ``None`` if unsure."""
    sample = text.strip()[:4000]
    if len(sample) < 20:
        return None
    for code, pattern in _SCRIPTS:
        if len(pattern.findall(sample)) > len(sample) * 0.3:
            return _refine_arabic_script(sample) if code == "ar" else code
    try:
        from langdetect import DetectorFactory, detect_langs  # type: ignore

        DetectorFactory.seed = 0
        best = detect_langs(sample)[0]
        if best.prob < 0.6:
            return None
        return best.lang.split("-")[0].lower()
    except Exception:
        return None
