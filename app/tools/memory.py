"""Explicit persistent memory tools for JARVIS."""

from __future__ import annotations

import json

from app.memory.models import Memory
from app.memory.store import MemoryStore

_store = MemoryStore()


def remember_memory(content: str, memory_type: str = "CONTEXT", importance: float = 0.5, confidence: float = 1.0, project: str | None = None, source: str = "explicit_user_instruction") -> str:
    memory_id = _store.add(Memory(None, content, memory_type, importance, confidence, source, project))
    if memory_id is None:
        return json.dumps({"success": False, "error": "Memory is empty or appears to contain a secret."})
    return json.dumps({"success": True, "id": memory_id})


def search_memory(query: str, limit: int = 5, project: str | None = None) -> str:
    return json.dumps({"success": True, "query": query, "memories": [memory.__dict__ for memory in _store.search(query, limit, project)]}, default=str, indent=2)


def list_memories(project: str | None = None) -> str:
    return json.dumps({"success": True, "memories": [memory.__dict__ for memory in _store.list(project)]}, default=str, indent=2)


def update_memory(memory_id: int, content: str, **fields) -> str:
    return json.dumps({"success": _store.update(int(memory_id), content, **fields)})


def supersede_memory(memory_id: int, content: str, **fields) -> str:
    replacement = Memory(None, content, **fields)
    replacement_id = _store.supersede(int(memory_id), replacement)
    return json.dumps({"success": replacement_id is not None, "id": replacement_id})


def forget_memory(memory_id: int) -> str:
    return json.dumps({"success": _store.remove(int(memory_id))})


def clear_memory() -> str:
    _store.clear()
    return json.dumps({"success": True})


def consolidate_memory(project: str | None = None) -> str:
    return json.dumps(_store.consolidate(project))


def memory_status(project: str | None = None) -> str:
    return json.dumps(_store.status(project))


# Backwards-compatible names used by earlier stages.
def remember(key: str, value) -> str:
    return remember_memory(f"{key}: {value}")


def recall(key: str) -> str:
    return search_memory(key)


def forget(key: str) -> str:
    return json.dumps({"success": _store.delete(key)})
