"""Knowledge tools for JARVIS."""

from __future__ import annotations

import json
from pathlib import Path

from app.knowledge.manager import KnowledgeManager

_manager = KnowledgeManager()


def index_file(path: str) -> str:
    return json.dumps(_manager.index_file(path), indent=2)


def index_directory(path: str, recursive: bool = True) -> str:
    return json.dumps(_manager.index_directory(path, recursive), indent=2)


def search_knowledge(query: str, limit: int = 5, project_path: str | None = None) -> str:
    if not query or not query.strip():
        return json.dumps({"success": False, "error": "Knowledge query cannot be empty."})
    return json.dumps(_manager.search(query, limit, project_path), indent=2)


def semantic_search(query: str, limit: int = 5, project_path: str | None = None) -> str:
    return search_knowledge(query, limit, project_path)


def get_document(path: str) -> str:
    return json.dumps(_manager.search(Path(path).stem, limit=20), indent=2)


def remove_document(path: str) -> str:
    return json.dumps({"success": _manager.database.remove(path)})


def knowledge_status() -> str:
    return json.dumps({"success": True, **_manager.database.status()}, indent=2)
