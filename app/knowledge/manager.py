"""Knowledge indexing and retrieval manager."""

from __future__ import annotations

from pathlib import Path

from app.knowledge.chunker import chunk_text
from app.knowledge.database import KnowledgeDatabase
from app.knowledge.loaders import SUPPORTED_EXTENSIONS, load_text

IGNORED = {".git", ".venv", "__pycache__", ".pytest_cache", "node_modules", "data"}
SECRET_NAMES = {".env", "credentials", "passwords", "id_rsa", "id_ed25519"}


class KnowledgeManager:
    def __init__(self, database: KnowledgeDatabase | None = None):
        self.database = database or KnowledgeDatabase()

    def index_file(self, path: str) -> dict:
        file_path = Path(path).resolve()
        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return {"success": False, "skipped": True, "reason": "Unsupported extension."}
        if any(part in SECRET_NAMES for part in file_path.parts) or file_path.name.lower() in SECRET_NAMES:
            return {"success": False, "skipped": True, "reason": "Sensitive file excluded."}
        try:
            content = load_text(file_path)
            indexed = self.database.index(str(file_path), content, file_path.stat().st_mtime, file_path.parent.name, chunk_text(content))
            return {"success": True, "indexed": indexed, "path": str(file_path)}
        except (OSError, ValueError, UnicodeError) as exc:
            return {"success": False, "error": str(exc)}

    def index_directory(self, path: str, recursive: bool = True) -> dict:
        root = Path(path).resolve()
        paths = root.rglob("*") if recursive else root.glob("*")
        results = [self.index_file(str(item)) for item in paths if item.is_file() and item.suffix.lower() in SUPPORTED_EXTENSIONS and not any(part in IGNORED for part in item.relative_to(root).parts)]
        return {"success": True, "indexed": sum(item.get("indexed", False) for item in results), "files": len(results)}

    def search(self, query: str, limit: int = 5, project: str | None = None) -> dict:
        return {"success": True, "query": query, "results": self.database.search(query, limit, project)}
