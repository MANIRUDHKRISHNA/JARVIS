import json
from pathlib import Path

from app.agent.indexer import build_change_impact


def create_project(tmp_path: Path):
    app_dir = tmp_path / "app"
    tests_dir = tmp_path / "tests"
    app_dir.mkdir()
    tests_dir.mkdir()
    (app_dir / "__init__.py").write_text("", encoding="utf-8")
    (app_dir / "brain.py").write_text("class Brain:\n    def think(self):\n        return 'thinking'\n", encoding="utf-8")
    (app_dir / "router.py").write_text("from app.brain import Brain\nbrain = Brain()\n", encoding="utf-8")
    (tests_dir / "test_brain.py").write_text("from app.brain import Brain\ndef test_brain():\n    assert Brain().think() == 'thinking'\n", encoding="utf-8")


def test_change_impact_detects_dependents(tmp_path):
    create_project(tmp_path)
    data = json.loads(build_change_impact(str(tmp_path), str(tmp_path / "app" / "brain.py")))
    assert data["success"] is True
    assert data["target_module"] == "app.brain"
    assert "app.router" in [item["from"] for item in data["dependents"]]


def test_change_impact_detects_dependencies(tmp_path):
    create_project(tmp_path)
    data = json.loads(build_change_impact(str(tmp_path), str(tmp_path / "app" / "router.py")))
    assert data["success"] is True
    assert "app.brain" in [item["to"] for item in data["dependencies"]]


def test_change_impact_rejects_outside_file(tmp_path):
    create_project(tmp_path)
    outside = tmp_path.parent / "outside.py"
    outside.write_text("print('outside')", encoding="utf-8")
    data = json.loads(build_change_impact(str(tmp_path), str(outside)))
    assert data["success"] is False
