"""Make extracted text pleasant for a speech engine: remove artefacts, fix line wrapping,
strip Markdown syntax. Pure functions, no I/O."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_ZERO_WIDTH = re.compile(r"[​‌‍⁠﻿­]")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_PAGE_NUMBER = re.compile(r"^\s*(?:page\s+)?\d{1,3}(?:\s*(?:/|of)\s*\d{1,3})?\s*$", re.I)
_PAGE_DASHED = re.compile(r"^\s*[-–—]\s*\d{1,3}\s*[-–—]\s*$")
_URL = re.compile(r"https?://\S+|www\.\S+", re.I)
_TERMINAL = ".!?:;…؟۔।。！？"


@dataclass
class CleaningOptions:
    fix_hyphenation: bool = True
    join_lines: bool = True
    remove_page_numbers: bool = True
    strip_markdown: bool = False
    remove_urls: bool = False


def _ends_sentence(line: str) -> bool:
    tail = line.rstrip(" \"'”’)]")
    return bool(tail) and tail[-1] in _TERMINAL


def _with_period(text: str) -> str:
    text = text.strip()
    return text if not text or _ends_sentence(text) else text + "."


def strip_markdown(text: str) -> str:
    """Remove Markdown syntax but keep the readable words. Headings and list items get a
    trailing full stop so the voice pauses naturally."""
    text = re.sub(r"```.*?```|~~~.*?~~~", " ", text, flags=re.S)
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\[[^\]]*\]", r"\1", text)
    text = re.sub(r"^\s{0,3}\[[^\]]+\]:\s+\S+.*$", "", text, flags=re.M)
    text = re.sub(r"<[^>\n]+>", " ", text)

    out: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if re.fullmatch(r"([-*_])\1{2,}", stripped.replace(" ", "")):
            out.append("")
            continue
        if re.fullmatch(r"\|?[ \t]*:?-{2,}:?[ \t]*(\|[ \t]*:?-{2,}:?[ \t]*)*\|?", stripped):
            continue
        heading = re.match(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$", line)
        if heading:
            out.append(_with_period(heading.group(1)))
            continue
        line = re.sub(r"^\s*>+\s?", "", line)
        item = re.match(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)$", line)
        if item:
            line = _with_period(item.group(1))
        if line.count("|") >= 2:
            cells = [c.strip() for c in line.strip().strip("|").split("|") if c.strip()]
            line = _with_period(", ".join(cells))
        out.append(line)
    text = "\n".join(out)

    text = re.sub(r"(\*\*|__)(.+?)\1", r"\2", text)
    text = re.sub(r"\*(?!\s)(.+?)(?<!\s)\*", r"\1", text)
    text = re.sub(r"(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)", r"\1", text)
    text = re.sub(r"~~(.+?)~~", r"\1", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    return text


def _join_wrapped_lines(text: str) -> str:
    """Re-join lines that were hard-wrapped (typical of PDFs) while keeping paragraph breaks."""
    paragraphs: list[str] = []
    for block in text.split("\n\n"):
        lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
        if not lines:
            continue
        merged: list[str] = [lines[0]]
        for line in lines[1:]:
            previous = merged[-1]
            if _ends_sentence(previous) and not line[:1].islower():
                merged.append(line)
            else:
                merged[-1] = f"{previous} {line}"
        paragraphs.append("\n".join(merged))
    return "\n\n".join(paragraphs)


def clean_text(text: str, options: CleaningOptions | None = None) -> str:
    o = options or CleaningOptions()
    t = unicodedata.normalize("NFKC", text)
    t = t.replace("\r\n", "\n").replace("\r", "\n").replace(" ", " ")
    t = _ZERO_WIDTH.sub("", t)
    t = _CONTROL.sub("", t)

    if o.strip_markdown:
        t = strip_markdown(t)
    if o.remove_urls:
        t = _URL.sub("", t)
    if o.remove_page_numbers:
        t = "\n".join(
            ln for ln in t.split("\n") if not (_PAGE_NUMBER.match(ln) or _PAGE_DASHED.match(ln))
        )
    if o.fix_hyphenation:
        t = re.sub(r"(?<=[A-Za-z])-[ \t]*\n[ \t]*(?=[a-z])", "", t)

    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    if o.join_lines:
        t = _join_wrapped_lines(t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()
