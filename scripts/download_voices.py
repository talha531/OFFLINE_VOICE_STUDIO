"""Download Piper voice models into models/piper (the only step that needs internet).

Usage (from the project folder, inside the virtual environment):

    python scripts/download_voices.py                      # starter set (4 voices)
    python scripts/download_voices.py --list               # show the curated catalogue
    python scripts/download_voices.py en_US-lessac-medium de_DE-thorsten-medium
    python scripts/download_voices.py --all-curated

Any voice key from https://huggingface.co/rhasspy/piper-voices works, not only the curated ones.
Only the Python standard library is used. Files that already exist are skipped.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
DEFAULT_DIR = Path(__file__).resolve().parent.parent / "models" / "piper"

# key -> (gender, display name). Gender is stored in a small sidecar file so the app's
# gender filter works; voices not listed here show as "unspecified".
CURATED: dict[str, tuple[str, str]] = {
    "en_US-lessac-medium": ("female", "Lessac"),
    "en_US-hfc_female-medium": ("female", "HFC Female"),
    "en_US-hfc_male-medium": ("male", "HFC Male"),
    "en_US-amy-medium": ("female", "Amy"),
    "en_US-joe-medium": ("male", "Joe"),
    "en_US-john-medium": ("male", "John"),
    "en_US-kristin-medium": ("female", "Kristin"),
    "en_GB-alan-medium": ("male", "Alan"),
    "en_GB-jenny_dioco-medium": ("female", "Jenny"),
    "en_GB-alba-medium": ("female", "Alba"),
    "en_GB-northern_english_male-medium": ("male", "Northern English"),
    "de_DE-thorsten-medium": ("male", "Thorsten"),
    "de_DE-kerstin-low": ("female", "Kerstin"),
    "ar_JO-kareem-medium": ("male", "Kareem"),
}
STARTER = ["en_US-lessac-medium", "en_US-hfc_male-medium", "en_GB-alan-medium", "en_GB-jenny_dioco-medium"]


def urls_for(key: str) -> tuple[str, str]:
    """``en_US-lessac-medium`` -> .../en/en_US/lessac/medium/en_US-lessac-medium.onnx (+ .json)."""
    parts = key.split("-")
    if len(parts) != 3 or "_" not in parts[0]:
        raise ValueError(f"'{key}' is not a Piper voice key (expected e.g. en_US-lessac-medium)")
    locale, name, quality = parts
    base = f"{BASE_URL}/{locale.split('_')[0]}/{locale}/{name}/{quality}/{key}.onnx"
    return base, base + ".json"


def fetch(url: str, target: Path) -> None:
    tmp = target.with_suffix(target.suffix + ".part")
    try:
        with urllib.request.urlopen(url, timeout=60) as response, open(tmp, "wb") as out:
            total = int(response.headers.get("Content-Length") or 0)
            done = 0
            while block := response.read(1 << 20):
                out.write(block)
                done += len(block)
                if total:
                    print(f"\r    {target.name}: {done / 1e6:6.1f} / {total / 1e6:.1f} MB", end="", flush=True)
        tmp.replace(target)
        print()
    finally:
        tmp.unlink(missing_ok=True)


def download(key: str, folder: Path) -> bool:
    try:
        model_url, config_url = urls_for(key)
    except ValueError as exc:
        print(f"  ! {exc}")
        return False
    model, config = folder / f"{key}.onnx", folder / f"{key}.onnx.json"
    print(f"  {key}")
    try:
        for url, target in ((config_url, config), (model_url, model)):
            if target.exists() and target.stat().st_size > 0:
                print(f"    {target.name}: already present")
            else:
                fetch(url, target)
    except (urllib.error.URLError, OSError) as exc:
        print(f"\n  ! Could not download {key}: {exc}")
        return False
    if key in CURATED:
        gender, display = CURATED[key]
        (folder / f"{key}.studio.json").write_text(json.dumps({"gender": gender, "display_name": display}), encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Download Piper voices for Offline Voice Studio.")
    parser.add_argument("voices", nargs="*", help="voice keys, e.g. en_US-lessac-medium (default: starter set)")
    parser.add_argument("--all-curated", action="store_true", help="download every voice in the curated list")
    parser.add_argument("--list", action="store_true", help="print the curated catalogue and exit")
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR, help=f"target folder (default: {DEFAULT_DIR})")
    args = parser.parse_args()

    if args.list:
        for key, (gender, display) in CURATED.items():
            print(f"{key:40s} {gender:7s} {display}")
        return 0

    keys = list(CURATED) if args.all_curated else (args.voices or STARTER)
    args.dir.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {len(keys)} voice(s) into {args.dir}")
    results = [download(k, args.dir) for k in keys]
    ok = sum(results)
    print(f"\nDone: {ok} of {len(keys)} voice(s) ready." + ("" if ok == len(keys) else " Check your connection and run again."))
    return 0 if ok == len(keys) else 1


if __name__ == "__main__":
    sys.exit(main())
