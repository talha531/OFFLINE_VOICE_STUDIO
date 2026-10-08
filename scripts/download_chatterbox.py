"""Download the Chatterbox Multilingual model into models/chatterbox (internet needed once, ~3.3 GB).

    python scripts/download_chatterbox.py

Standard library only. Existing files are skipped; re-run to resume after a failure.
Check https://huggingface.co/ResembleAI/chatterbox for the licence terms.
"""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIR = ROOT / "models" / "chatterbox"
BASE = "https://huggingface.co/ResembleAI/chatterbox/resolve/main/{name}"
FILES = ("grapheme_mtl_merged_expanded_v1.json", "Cangjie5_TC.json", "conds.pt", "ve.pt", "s3gen.pt", "t3_mtl23ls_v2.safetensors")


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
    parser = argparse.ArgumentParser(description="Download the Chatterbox Multilingual model.")
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    args = parser.parse_args()
    args.dir.mkdir(parents=True, exist_ok=True)
    print(f"Downloading Chatterbox Multilingual into {args.dir}")
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
    print("\nDone. Install the engine packages once:  uv pip install -r requirements-chatterbox.txt   then restart the app.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
