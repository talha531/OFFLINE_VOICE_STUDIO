"""Prints which speech and cloning engines are ready, and exactly what is missing.

    .venv\\Scripts\\python.exe scripts\\check_setup.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from studio.bootstrap import bootstrap  # noqa: E402
from studio.engines.registry import get_tts_engine, list_cloning_engines, plugin_load_errors  # noqa: E402


def main() -> int:
    bootstrap()
    print(f"Python {sys.version.split()[0]}\n")
    tts = get_tts_engine()
    voices = tts.list_voices()
    langs = sorted({v.language_name for v in voices})
    print("Standard voices:", f"{len(voices)} ready ({', '.join(langs)})" if voices else "NONE")
    if not voices:
        status = tts.status()
        print("  ->", status.message)
        for hint in status.hints:
            print("    *", hint)

    print("\nVoice cloning engines:")
    ready = False
    for engine in list_cloning_engines():
        status = engine.status()
        ready = ready or status.available
        print(f"  [{'OK' if status.available else '--'}] {engine.name}: {status.message}")
        if not status.available:
            for hint in status.hints:
                print("       *", hint)
    for name, message in plugin_load_errors().items():
        print(f"  [!!] plugin {name} failed to load: {message}")
    if not ready:
        print("\nNo cloning engine is ready. Double-click install_voice_cloning.bat, then restart the app.")
    return 0 if (voices and ready) else 1


if __name__ == "__main__":
    sys.exit(main())
