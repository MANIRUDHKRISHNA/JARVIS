"""Text chunking for local knowledge."""

from __future__ import annotations


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 120) -> list[str]:
    words = text.split()
    if not words:
        return []
    step = max(1, chunk_size - overlap)
    return [" ".join(words[index:index + chunk_size]) for index in range(0, len(words), step)]
