"""Download the Coqui XTTS-v2 voice-cloning model into models/xtts (needs internet once, ~2 GB).

    python scripts/download_xtts.py

LICENCE: XTTS-v2 uses the Coqui Public Model License (non-commercial use only).
Standard library only. Existing files are skipped; interrupted downloads can simply be re-run.
"""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIR = ROOT / "models" / "xtts"
BASE = "https://huggingface.co/coqui/XTTS-v2/resolve/main/{name}"
FILES = ("config.json", "vocab.json", "speakers_xtts.pth", "mel_stats.pth", "model.pth")  # model.pth is the big one


def fetch(url: str, target: Path) -> None:
    tmp = target.with_suffix(target.suffix + ".part")
    try:
        with urllib.request.urlopen(url, timeout=60) as response, open(tmp, "wb") as out:
            total = int(response.headers.get("Content-Length") or 0)
            done = 0
            while block := response.read(1 << 20):
                out.write(block)
                done += len(block)
                if total > 5_000_000:
                    print(f"\r    {target.name}: {done / 1e6:7.1f} / {total / 1e6:.1f} MB", end="", flush=True)
        tmp.replace(target)
        if total > 5_000_000:
            print()
    finally:
        tmp.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Download the XTTS-v2 cloning model.")
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    args = parser.parse_args()
    args.dir.mkdir(parents=True, exist_ok=True)
    print(f"Downloading XTTS-v2 into {args.dir}  (Coqui Public Model License, non-commercial)")
    try:
        for name in FILES:
            target = args.dir / name
            if target.exists() and target.stat().st_size > 0:
                print(f"  {name}: already present")
                continue
            print(f"  {name}")
            fetch(BASE.format(name=name), target)
    except (urllib.error.URLError, OSError) as exc:
        print(f"\n  ! Download failed: {exc}\n  Check your connection and run the script again.")
        return 1
    print("\nDone. Install the engine packages once:  uv pip install -r requirements-cloning.txt   then restart the app.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
