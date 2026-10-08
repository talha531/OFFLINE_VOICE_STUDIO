"""Sentence-aware chunking so very large documents can be synthesised piece by piece."""

from __future__ import annotations

import re
from dataclasses import dataclass

_SENTENCE_BREAK = re.compile(
    r"(?<=[.!?…؟۔।。！？][\"'”’)\]])\s+"
    r"|(?<=[.!?…؟۔।。！？])\s+"
)
_CLAUSE_BREAK = re.compile(r"(?<=[,;:—–،])\s+")
_ABBREVIATIONS = {
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "vs", "etc", "e.g", "i.e", "no", "fig", "inc", "ltd", "co",
    "approx", "dept", "est", "vol",
}
_TERMINAL = ".!?:;…؟۔।。！？"
CHARS_PER_SECOND = 15.0  # about 150 words per minute at normal speed


@dataclass(frozen=True)
class Chunk:
    index: int
    text: str
    ends_paragraph: bool = False


def _is_abbreviation_end(sentence: str) -> bool:
    match = re.search(r"([\w.]+)\.$", sentence.strip())
    if not match:
        return False
    token = match.group(1)
    return token.lower() in _ABBREVIATIONS or (len(token) == 1 and token.isalpha() and token.isupper())


def split_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in _SENTENCE_BREAK.split(text.strip()) if p and p.strip()]
    merged: list[str] = []
    for part in parts:
        if merged and _is_abbreviation_end(merged[-1]):
            merged[-1] = f"{merged[-1]} {part}"
        else:
            merged.append(part)
    return merged


def _split_long(sentence: str, max_chars: int) -> list[str]:
    """Break an over-long sentence at clause marks, then at spaces."""
    if len(sentence) <= max_chars:
        return [sentence]
    pieces: list[str] = []
    current = ""
    for clause in _CLAUSE_BREAK.split(sentence):
        if len(clause) > max_chars:
            if current:
                pieces.append(current)
                current = ""
            words, line = clause.split(), ""
            for word in words:
                if line and len(line) + 1 + len(word) > max_chars:
                    pieces.append(line)
                    line = word
                else:
                    line = f"{line} {word}".strip()
            current = line
        elif current and len(current) + 1 + len(clause) > max_chars:
            pieces.append(current)
            current = clause
        else:
            current = f"{current} {clause}".strip()
    if current:
        pieces.append(current)
    return pieces


def chunk_text(text: str, max_chars: int = 450) -> list[Chunk]:
    """Split ``text`` into chunks of at most ``max_chars`` characters, never cutting a sentence
    unless a single sentence exceeds the limit. Chunks that end a paragraph are flagged so the
    pipeline can insert a longer pause."""
    max_chars = max(80, int(max_chars))
    chunks: list[Chunk] = []

    def flush(buffer: list[str], paragraph_end: bool) -> None:
        if buffer:
            chunks.append(Chunk(len(chunks), " ".join(buffer), paragraph_end))

    for paragraph in re.split(r"\n\s*\n", text.strip()):
        if not paragraph.strip():
            continue
        sentences: list[str] = []
        for line in paragraph.split("\n"):
            line = line.strip()
            if not line:
                continue
            if len(line) < 80 and line[-1] not in _TERMINAL and "\n" in paragraph:
                line += "."  # heading / list-like line: gives the voice a natural stop
            sentences.extend(split_sentences(line))

        buffer: list[str] = []
        size = 0
        for sentence in sentences:
            for piece in _split_long(sentence, max_chars):
                if buffer and size + 1 + len(piece) > max_chars:
                    flush(buffer, False)
                    buffer, size = [], 0
                buffer.append(piece)
                size += len(piece) + (1 if size else 0)
        flush(buffer, True)
    return chunks


def estimate_seconds(text: str, speed: float = 1.0) -> float:
    """Rough spoken duration, for display only."""
    return len(text.strip()) / CHARS_PER_SECOND / max(0.25, speed)
