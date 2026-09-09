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
        memory.confidence = max(0.0, min(1.0, float(memory.confidence)))
        memory.importance = max(0.0, min(1.0, float(memory.importance)))
        with self._lock, self._connect() as db:
            row = db.execute("SELECT id FROM memories WHERE content = ? AND project IS ? AND superseded_by IS NULL", (memory.content.strip(), memory.project)).fetchone()
            if row:
                return int(row["id"])
            cursor = db.execute("""INSERT INTO memories
                (content, memory_type, importance, confidence, source, project,
                 created_at, updated_at, last_accessed, access_count, superseded_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (memory.content.strip(), memory.memory_type, memory.importance, memory.confidence, memory.source, memory.project, now, now, None, 0, None))
            return cursor.lastrowid

    def supersede(self, memory_id: int, replacement: Memory) -> int | None:
        """Preserve an old fact while making a replacement the active one."""
        if self._sensitive(replacement.content):
            return None
        with self._lock, self._connect() as db:
            old = db.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
            if old is None or old["superseded_by"] is not None:
                return None
            replacement.project = replacement.project if replacement.project is not None else old["project"]
            if not replacement.content.strip():
                return None
            now = self._now()
            cursor = db.execute("""INSERT INTO memories
                (content, memory_type, importance, confidence, source, project, created_at, updated_at, last_accessed, access_count, superseded_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (replacement.content.strip(), replacement.memory_type, max(0.0, min(1.0, float(replacement.importance))), max(0.0, min(1.0, float(replacement.confidence))), replacement.source, replacement.project, now, now, None, 0, None))
            replacement_id = cursor.lastrowid
            db.execute("UPDATE memories SET superseded_by = ?, updated_at = ? WHERE id = ?", (replacement_id, self._now(), memory_id))
            db.execute("INSERT INTO memory_history (memory_id, content, changed_at) VALUES (?, ?, ?)", (memory_id, old["content"], self._now()))
            return replacement_id

    def search(self, query: str, limit: int = 5, project: str | None = None, minimum_confidence: float = 0.0) -> list[Memory]:
        terms = [term.lower() for term in re.findall(r"\w+", query or "")]
        if not terms:
            return []
        with self._lock, self._connect() as db:
            rows = db.execute("SELECT * FROM memories WHERE superseded_by IS NULL" + (" AND project = ?" if project else ""), (project,) if project else ()).fetchall()
            scored = []
            for row in rows:
                if row["confidence"] < max(0.0, min(1.0, minimum_confidence)):
                    continue
                relevance = sum(term in row["content"].lower() for term in terms) / len(terms)
                if relevance:
                    # Keep retrieval local and bounded.  Recency is deliberately a
                    # small tiebreaker, never a substitute for relevance/evidence.
                    age_days = max(0.0, (datetime.now(timezone.utc) - datetime.fromisoformat(row["updated_at"])).total_seconds() / 86400)
                    recency = 1.0 / (1.0 + age_days / 30.0)
                    type_bonus = 0.08 if row["memory_type"] in {"GOAL", "DECISION", "PREFERENCE"} else 0.0
                    scored.append((relevance * 0.52 + row["importance"] * 0.20 + row["confidence"] * 0.18 + recency * 0.02 + type_bonus, row))
            scored.sort(key=lambda item: item[0], reverse=True)
            result = [self._from_row(row) for _, row in scored[:max(1, limit)]]
            for memory in result:
                db.execute("UPDATE memories SET access_count = access_count + 1, last_accessed = ? WHERE id = ?", (self._now(), memory.id))
            return result

    def update(self, memory_id: int, content: str, **fields) -> bool:
        if not content.strip() or self._sensitive(content):
            return False
        values = {key: value for key, value in fields.items() if key in {"memory_type", "importance", "confidence", "project"}}
        values.update({"content": content, "updated_at": self._now()})
        assignments = ", ".join(f"{key} = ?" for key in values)
        with self._connect() as db:
            old = db.execute("SELECT content FROM memories WHERE id = ?", (memory_id,)).fetchone()
            if old is None:
                return False
            cursor = db.execute(f"UPDATE memories SET {assignments} WHERE id = ?", (*values.values(), memory_id))
            if cursor.rowcount:
                db.execute("INSERT INTO memory_history (memory_id, content, changed_at) VALUES (?, ?, ?)", (memory_id, old["content"], self._now()))
            return cursor.rowcount == 1

    def remove(self, memory_id: int) -> bool:
        with self._connect() as db:
            return db.execute("DELETE FROM memories WHERE id = ?", (memory_id,)).rowcount == 1

    def list(self, project: str | None = None) -> list[Memory]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM memories WHERE superseded_by IS NULL" + (" AND project = ?" if project else "") + " ORDER BY importance DESC, id DESC", (project,) if project else ()).fetchall()
            return [self._from_row(row) for row in rows]

    def consolidate(self, project: str | None = None, limit: int = 100) -> dict:
        """Mark exact normalized duplicates as superseded; preserve history."""
        memories = self.list(project)[:max(1, limit)]
        groups: dict[tuple[str, str | None], list[Memory]] = {}
        for memory in memories:
            key = (" ".join(memory.content.lower().split()), memory.project)
            groups.setdefault(key, []).append(memory)
        superseded = []
        with self._connect() as db:
            for duplicates in groups.values():
                if len(duplicates) < 2:
                    continue
                keeper = max(duplicates, key=lambda item: (item.confidence, item.importance, item.id or 0))
                for item in duplicates:
                    if item.id != keeper.id:
                        db.execute("UPDATE memories SET superseded_by = ?, updated_at = ? WHERE id = ?", (keeper.id, self._now(), item.id))
                        superseded.append(item.id)
        return {"success": True, "superseded": superseded, "kept": len(memories) - len(superseded)}

    def status(self, project: str | None = None) -> dict:
        return {"success": True, "active_memories": len(self.list(project)), "project": project}

    def context(self, query: str, project: str | None = None, max_items: int = 5, max_characters: int = 1200) -> list[Memory]:
        """Return only evidence-backed, relevant memories that fit a prompt budget."""
        selected, used = [], 0
        for memory in self.search(query, limit=max_items * 3, project=project, minimum_confidence=0.4):
            size = len(memory.content)
            if selected and used + size > max(1, max_characters):
                continue
            if size > max_characters:
                continue
            selected.append(memory)
            used += size
            if len(selected) >= max(1, max_items):
                break
        return selected

    @staticmethod
    def _from_row(row) -> Memory:
        return Memory(**dict(row))
