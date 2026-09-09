from app.memory.models import Memory
from app.memory.store import MemoryStore


def test_project_memory_isolation_and_consolidation(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    first = store.add(Memory(None, "Prefer dark mode", project="jarvis", confidence=1.0))
    store.add(Memory(None, "  prefer dark mode ", project="jarvis", confidence=0.5))
    store.add(Memory(None, "Prefer dark mode", project="travel", confidence=1.0))
    result = store.consolidate("jarvis")
    assert result["success"] and len(result["superseded"]) == 1
    assert [item.id for item in store.search("dark", project="jarvis")] == [first]
    assert len(store.search("dark", project="travel")) == 1


def test_secret_memory_is_refused(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    assert store.add(Memory(None, "api key is private")) is None
