"""Semantic-search compatibility layer."""

from __future__ import annotations

from app.knowledge.manager import KnowledgeManager


def semantic_search(query: str, limit: int = 5, project_path: str | None = None) -> dict:
    """Use local knowledge retrieval; embeddings remain optional."""
    return KnowledgeManager().search(query, limit, project_path)
