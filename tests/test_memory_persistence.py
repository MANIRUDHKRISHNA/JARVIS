from app.memory.models import Memory
from app.memory.store import MemoryStore


def test_memory_survives_restart(tmp_path):
    path = tmp_path / "memory.db"
    first = MemoryStore(path)
    assert first.add(Memory(None, "JARVIS stays local", "PREFERENCE", 1.0))
    second = MemoryStore(path)
    assert second.search("local")[0].content == "JARVIS stays local"


def test_duplicate_memory_is_consolidated(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    first = store.add(Memory(None, "Use Python", "FACT"))
    second = store.add(Memory(None, "Use Python", "FACT"))
    assert first == second
    assert len(store.list()) == 1


def test_secrets_are_rejected(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    assert store.add(Memory(None, "my api key is secret", "FACT")) is None
