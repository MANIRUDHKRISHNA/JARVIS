"""SQLite storage for local knowledge chunks."""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parents[2] / "data" / "knowledge.db"


class KnowledgeDatabase:
    def __init__(self, path: str | Path = DEFAULT_DB):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS documents (path TEXT PRIMARY KEY, file_hash TEXT NOT NULL, modified REAL NOT NULL, project TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS chunks (id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT NOT NULL, content TEXT NOT NULL, chunk_index INTEGER NOT NULL, project TEXT)")

    def _connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def index(self, path: str, content: str, modified: float, project: str | None, chunks: list[str]) -> bool:
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        with self._connect() as db:
            old = db.execute("SELECT file_hash FROM documents WHERE path = ?", (path,)).fetchone()
            if old and old["file_hash"] == digest:
                return False
            db.execute("DELETE FROM chunks WHERE path = ?", (path,))
            db.execute("INSERT OR REPLACE INTO documents(path, file_hash, modified, project) VALUES (?, ?, ?, ?)", (path, digest, modified, project))
            db.executemany("INSERT INTO chunks(path, content, chunk_index, project) VALUES (?, ?, ?, ?)", [(path, chunk, index, project) for index, chunk in enumerate(chunks)])
        return True

    def search(self, query: str, limit: int = 5, project: str | None = None) -> list[dict]:
        terms = [term.lower() for term in query.split() if term.strip()]
        if not terms:
            return []
        with self._connect() as db:
            rows = db.execute("SELECT * FROM chunks" + (" WHERE project = ?" if project else ""), (project,) if project else ()).fetchall()
        results = []
        for row in rows:
            text = row["content"].lower()
            score = sum(term in text for term in terms) / len(terms)
            if score:
                results.append({"score": score, "source": row["path"], "content": row["content"], "chunk_index": row["chunk_index"], "project": row["project"]})
        return sorted(results, key=lambda item: (-item["score"], item["source"]))[:max(1, limit)]

    def remove(self, path: str) -> bool:
        with self._connect() as db:
            db.execute("DELETE FROM chunks WHERE path = ?", (path,))
            return db.execute("DELETE FROM documents WHERE path = ?", (path,)).rowcount == 1

    def status(self) -> dict:
        with self._connect() as db:
            documents = db.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            chunks = db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        return {"documents": documents, "chunks": chunks, "database": str(self.path)}
