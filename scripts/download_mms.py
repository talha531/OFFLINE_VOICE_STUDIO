"""Download Meta MMS-TTS language models into models/mms (the only step that needs internet).

    python scripts/download_mms.py urd-script_arabic hin ara     # Urdu, Hindi, Arabic
    python scripts/download_mms.py --list                        # curated language codes
    python scripts/download_mms.py --all-curated                 # every curated language (large)

Any ISO 639-3 code works (Meta publishes about 1,100: https://huggingface.co/facebook/mms-tts).
If a language has no model you get a clear "not available" message. Each model is ~140 MB.
Standard library only. Existing files are skipped.

LICENCE: MMS-TTS models are CC-BY-NC 4.0 - non-commercial use only.
"""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from studio.engines.mms_catalog import MMS_LANGUAGES  # noqa: E402

DEFAULT_DIR = ROOT / "models" / "mms"
BASE = "https://huggingface.co/facebook/mms-tts-{code}/resolve/main/{name}"
REQUIRED = ("config.json", "vocab.json", "tokenizer_config.json")
OPTIONAL = ("special_tokens_map.json", "added_tokens.json")
WEIGHTS = ("model.safetensors", "pytorch_model.bin")  # first one that exists is used


def fetch(url: str, target: Path) -> bool:
    """Download ``url``; return False on HTTP 404, raise on other errors."""
    tmp = target.with_suffix(target.suffix + ".part")
    try:
        with urllib.request.urlopen(url, timeout=60) as response, open(tmp, "wb") as out:
            total = int(response.headers.get("Content-Length") or 0)
            done = 0
            while block := response.read(1 << 20):
                out.write(block)
                done += len(block)
                if total > 5_000_000:
                    print(f"\r    {target.name}: {done / 1e6:6.1f} / {total / 1e6:.1f} MB", end="", flush=True)
        tmp.replace(target)
        if total > 5_000_000:
            print()
        return True
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False
        raise
    finally:
        tmp.unlink(missing_ok=True)


def download(code: str, root: Path) -> bool:
    name = MMS_LANGUAGES.get(code, ("", code))[1]
    folder = root / code
    folder.mkdir(parents=True, exist_ok=True)
    print(f"  {code}  ({name})")
    try:
        for file in REQUIRED:
            if (folder / file).exists():
                continue
            if not fetch(BASE.format(code=code, name=file), folder / file):
                print(f"  ! No MMS model is published for '{code}' (file {file} not found).")
                if not any(folder.iterdir()):
                    folder.rmdir()
                return False
        for file in OPTIONAL:
            if not (folder / file).exists():
                fetch(BASE.format(code=code, name=file), folder / file)
        if not any((folder / w).exists() for w in WEIGHTS):
            if not any(fetch(BASE.format(code=code, name=w), folder / w) for w in WEIGHTS):
                print(f"  ! Model weights for '{code}' were not found.")
                return False
    except (urllib.error.URLError, OSError) as exc:
        print(f"\n  ! Could not download '{code}': {exc}")
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Download MMS-TTS language models.")
    parser.add_argument("languages", nargs="*", help="ISO 639-3 codes, e.g. urd-script_arabic hin ara")
    parser.add_argument("--all-curated", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    args = parser.parse_args()

    if args.list:
        for code, (family, name) in MMS_LANGUAGES.items():
            print(f"{code:20s} {family:3s} {name}")
        return 0
    codes = list(MMS_LANGUAGES) if args.all_curated else args.languages
    if not codes:
        parser.error("name at least one language code, e.g.: urd-script_arabic hin ara (see --list)")
    args.dir.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {len(codes)} language model(s) into {args.dir}  (CC-BY-NC 4.0, non-commercial)")
    ok = sum(download(c, args.dir) for c in codes)
    print(f"\nDone: {ok} of {len(codes)} ready. Install the engine packages once: uv pip install -r requirements-mms.txt")
    return 0 if ok == len(codes) else 1


if __name__ == "__main__":
    sys.exit(main())
