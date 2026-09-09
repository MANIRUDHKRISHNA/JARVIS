"""SQLite-backed persistent memory store for JARVIS."""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

from app.memory.models import Memory

DEFAULT_DB = Path(__file__).resolve().parents[2] / "data" / "memory.db"
_SECRET_PATTERNS = (r"(?i)\b(api[_ -]?key|token|password|secret|private key)\b", r"-----BEGIN .* PRIVATE KEY-----")


class MemoryStore:
    """Durable memory store with backwards-compatible key/value methods."""

    def __init__(self, path: str | Path = DEFAULT_DB):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._legacy: dict[str, object] = {}
        self._init_db()

    def _connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self):
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    importance REAL NOT NULL,
                    confidence REAL NOT NULL,
                    source TEXT NOT NULL,
                    project TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_accessed TEXT,
                    access_count INTEGER NOT NULL DEFAULT 0,
                    superseded_by INTEGER
                );
                CREATE TABLE IF NOT EXISTS memory_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    memory_id INTEGER,
                    content TEXT NOT NULL,
                    changed_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_memories_project ON memories(project);
            """)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _sensitive(content: str) -> bool:
        return any(re.search(pattern, content) for pattern in _SECRET_PATTERNS)

    def set(self, key: str, value) -> bool:
        if not key or not key.strip():
            return False
        self._legacy[key.strip()] = value
        return True

    def get(self, key: str, default=None):
        return self._legacy.get(key, default)

    def delete(self, key: str) -> bool:
        return self._legacy.pop(key, None) is not None

    def all(self):
        return dict(self._legacy)

    def clear(self):
        self._legacy.clear()
        with self._connect() as db:
            db.execute("DELETE FROM memories")

    def add(self, memory: Memory) -> int | None:
        if not memory.content.strip() or self._sensitive(memory.content):
            return None
        now = self._now()
        with self._lock, self._connect() as db:
            row = db.execute("SELECT id FROM memories WHERE content = ? AND superseded_by IS NULL", (memory.content.strip(),)).fetchone()
            if row:
                return int(row["id"])
            cursor = db.execute("""INSERT INTO memories
                (content, memory_type, importance, confidence, source, project,
                 created_at, updated_at, last_accessed, access_count, superseded_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (memory.content.strip(), memory.memory_type, memory.importance, memory.confidence, memory.source, memory.project, now, now, None, 0, None))
            return cursor.lastrowid

    def search(self, query: str, limit: int = 5, project: str | None = None) -> list[Memory]:
        terms = [term.lower() for term in re.findall(r"\w+", query or "")]
        if not terms:
            return []
        with self._lock, self._connect() as db:
            rows = db.execute("SELECT * FROM memories WHERE superseded_by IS NULL" + (" AND project = ?" if project else ""), (project,) if project else ()).fetchall()
            scored = []
            for row in rows:
                relevance = sum(term in row["content"].lower() for term in terms) / len(terms)
                if relevance:
                    scored.append((relevance * 0.5 + row["importance"] * 0.25 + row["confidence"] * 0.15, row))
            scored.sort(key=lambda item: item[0], reverse=True)
            result = [self._from_row(row) for _, row in scored[:max(1, limit)]]
            for memory in result:
                db.execute("UPDATE memories SET access_count = access_count + 1, last_accessed = ? WHERE id = ?", (self._now(), memory.id))
            return result

    def update(self, memory_id: int, content: str, **fields) -> bool:
        if self._sensitive(content):
            return False
        values = {key: value for key, value in fields.items() if key in {"memory_type", "importance", "confidence", "project"}}
        values.update({"content": content, "updated_at": self._now()})
        assignments = ", ".join(f"{key} = ?" for key in values)
        with self._connect() as db:
            cursor = db.execute(f"UPDATE memories SET {assignments} WHERE id = ?", (*values.values(), memory_id))
            return cursor.rowcount == 1

    def remove(self, memory_id: int) -> bool:
        with self._connect() as db:
            return db.execute("DELETE FROM memories WHERE id = ?", (memory_id,)).rowcount == 1

    def list(self, project: str | None = None) -> list[Memory]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM memories WHERE superseded_by IS NULL" + (" AND project = ?" if project else "") + " ORDER BY importance DESC, id DESC", (project,) if project else ()).fetchall()
            return [self._from_row(row) for row in rows]

    @staticmethod
    def _from_row(row) -> Memory:
        return Memory(**dict(row))
