"""Data only: Meta MMS-TTS language codes (ISO 639-3) -> (language family, display name).

MMS-TTS publishes one model per language as ``facebook/mms-tts-<code>``. Meta covers roughly
1,100 languages; this list is a convenient subset. Any code works with
``scripts/download_mms.py`` - if Meta has no model for it, the download reports that clearly.
Must stay import-light (no heavy dependencies): the download script imports it.
"""

from __future__ import annotations

MMS_LANGUAGES: dict[str, tuple[str, str]] = {
    "urd-script_arabic": ("ur", "Urdu"),
    "hin": ("hi", "Hindi"),
    "ara": ("ar", "Arabic"),
    "pan": ("pa", "Punjabi"),
    "pus": ("ps", "Pashto"),
    "snd": ("sd", "Sindhi"),
    "fas": ("fa", "Persian"),
    "ben": ("bn", "Bengali"),
    "tam": ("ta", "Tamil"),
    "tel": ("te", "Telugu"),
    "mal": ("ml", "Malayalam"),
    "kan": ("kn", "Kannada"),
    "guj": ("gu", "Gujarati"),
    "mar": ("mr", "Marathi"),
    "eng": ("en", "English"),
    "fra": ("fr", "French"),
    "deu": ("de", "German"),
    "spa": ("es", "Spanish"),
    "por": ("pt", "Portuguese"),
    "rus": ("ru", "Russian"),
    "tur": ("tr", "Turkish"),
    "vie": ("vi", "Vietnamese"),
    "tha": ("th", "Thai"),
    "ind": ("id", "Indonesian"),
    "swh": ("sw", "Swahili"),
    "hau": ("ha", "Hausa"),
    "yor": ("yo", "Yoruba"),
    "kor": ("ko", "Korean"),
    "nld": ("nl", "Dutch"),
    "pol": ("pl", "Polish"),
    "ron": ("ro", "Romanian"),
    "hun": ("hu", "Hungarian"),
    "ukr": ("uk", "Ukrainian"),
    "bul": ("bg", "Bulgarian"),
    "ell": ("el", "Greek"),
}


def describe(code: str) -> tuple[str, str]:
    """(language family, display name) for an MMS code; unknown codes are shown as-is."""
    if code in MMS_LANGUAGES:
        return MMS_LANGUAGES[code]
    base = code.split("-")[0]
    return base, base.upper()
