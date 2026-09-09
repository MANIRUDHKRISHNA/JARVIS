"""Local knowledge document models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Chunk:
    source: str
    content: str
    chunk_index: int
    line_start: int | None = None
    line_end: int | None = None
    project: str | None = None
