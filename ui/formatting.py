"""Small, pure helpers that turn numbers and timestamps into friendly text."""

from __future__ import annotations

from datetime import datetime


def fmt_duration(seconds: float | None) -> str:
    """``83`` -> ``1:23``; ``3725`` -> ``1:02:05``."""
    total = int(round(seconds or 0))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def fmt_duration_words(seconds: float | None) -> str:
    total = int(round(seconds or 0))
    if total < 60:
        return f"{total} s"
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours} h {minutes:02d} min"
    return f"{minutes} min {secs:02d} s" if secs else f"{minutes} min"


def fmt_size(num_bytes: float | None) -> str:
    size = float(num_bytes or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def fmt_when(iso: str | None) -> str:
    if not iso:
        return "-"
    try:
        moment = datetime.fromisoformat(iso)
    except ValueError:
        return iso
    now = datetime.now(moment.tzinfo)
    days = (now.date() - moment.date()).days
    clock = moment.strftime("%H:%M")
    if days == 0:
        return f"Today, {clock}"
    if days == 1:
        return f"Yesterday, {clock}"
    return f"{moment.day} {moment.strftime('%b %Y')}, {clock}"


def plural(count: int, word: str, many: str | None = None) -> str:
    return f"{count:,} {word if count == 1 else (many or word + 's')}"


def truncate(text: str, limit: int = 80) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def greeting(hour: int | None = None) -> str:
    hour = datetime.now().hour if hour is None else hour
    if hour < 5:
        return "Working late"
    if hour < 12:
        return "Good morning"
    if hour < 18:
        return "Good afternoon"
    return "Good evening"
