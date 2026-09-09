"""Persistent memory data models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class MemoryType(StrEnum):
    FACT = "FACT"
    PREFERENCE = "PREFERENCE"
    GOAL = "GOAL"
    DECISION = "DECISION"
    PROJECT = "PROJECT"
    CONTEXT = "CONTEXT"
    KNOWLEDGE = "KNOWLEDGE"


@dataclass
class Memory:
    id: int | None
    content: str
    memory_type: str = MemoryType.CONTEXT
    importance: float = 0.5
    confidence: float = 1.0
    source: str = "user"
    project: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    last_accessed: str | None = None
    access_count: int = 0
    superseded_by: int | None = None
