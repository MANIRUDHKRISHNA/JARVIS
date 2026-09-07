import json

from app.agent.health import diagnose_runtime, record_crash
from app.agent.model_manager import ModelManager
from app.tools.runtime import diagnose_runtime as diagnose_runtime_tool


def test_runtime_diagnostics_structure():
    result = diagnose_runtime(ModelManager(command=[]))
    assert {"gpu", "cuda", "model_alive", "cpu", "ram"} <= result.keys()
    assert result["model_alive"] is False
    assert isinstance(result["gpu"], bool)
    assert isinstance(result["cuda"], bool)


def test_runtime_tool_returns_json():
    data = json.loads(diagnose_runtime_tool())
    assert "model_alive" in data


def test_crash_record_is_searchable(tmp_path, monkeypatch):
    import app.agent.health as health
    monkeypatch.setattr(health, "CRASH_DIR", tmp_path)
    path = record_crash("test failure", gpu=False, ram=42)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["error"] == "test failure"
    assert data["gpu"] is False
    assert data["ram"] == 42
