import json

from app.knowledge.chunker import chunk_text
from app.knowledge.database import KnowledgeDatabase
from app.knowledge.manager import KnowledgeManager


def test_chunking_overlap():
    chunks = chunk_text("one two three four five six", chunk_size=4, overlap=1)
    assert len(chunks) >= 2
    assert "four" in chunks[0]
    assert "four" in chunks[1]


def test_index_and_search_text(tmp_path):
    source = tmp_path / "notes.md"
    source.write_text("JARVIS should remain fully local and private.", encoding="utf-8")
    manager = KnowledgeManager(KnowledgeDatabase(tmp_path / "knowledge.db"))
    result = manager.index_file(str(source))
    assert result["success"] is True
    matches = manager.search("local private")
    assert matches["results"][0]["source"] == str(source.resolve())


def test_unchanged_file_is_skipped(tmp_path):
    source = tmp_path / "notes.txt"
    source.write_text("hello knowledge", encoding="utf-8")
    manager = KnowledgeManager(KnowledgeDatabase(tmp_path / "knowledge.db"))
    assert manager.index_file(str(source))["indexed"] is True
    assert manager.index_file(str(source))["indexed"] is False


def test_secret_file_is_excluded(tmp_path):
    source = tmp_path / ".env"
    source.write_text("TOKEN=hidden", encoding="utf-8")
    manager = KnowledgeManager(KnowledgeDatabase(tmp_path / "knowledge.db"))
    assert manager.index_file(str(source))["skipped"] is True
