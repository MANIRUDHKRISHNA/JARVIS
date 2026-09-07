import json
from pathlib import Path

from app.tools.code_index import select_tests_for_change


def create_project(tmp_path: Path):
    app_dir = tmp_path / "app"
    tests_dir = tmp_path / "tests"
    app_dir.mkdir()
    tests_dir.mkdir()
    (app_dir / "__init__.py").write_text("", encoding="utf-8")
    (app_dir / "brain.py").write_text("class Brain:\n    def think(self):\n        return 'thinking'\n", encoding="utf-8")
    (app_dir / "router.py").write_text("from app.brain import Brain\nbrain = Brain()\n", encoding="utf-8")
    (tests_dir / "test_brain.py").write_text("from app.brain import Brain\ndef test_brain():\n    assert Brain().think() == 'thinking'\n", encoding="utf-8")
    (tests_dir / "test_router.py").write_text("from app.router import brain\ndef test_router():\n    assert brain is not None\n", encoding="utf-8")
    (tests_dir / "test_unrelated.py").write_text("def test_unrelated():\n    assert 1 + 1 == 2\n", encoding="utf-8")


def test_selects_relevant_brain_test(tmp_path):
    create_project(tmp_path)
    data = json.loads(select_tests_for_change(str(tmp_path), str(tmp_path / "app" / "brain.py")))
    assert data["success"] is True
    assert "tests/test_brain.py" in data["selected_tests"]


def test_does_not_prioritize_unrelated_test(tmp_path):
    create_project(tmp_path)
    data = json.loads(select_tests_for_change(str(tmp_path), str(tmp_path / "app" / "brain.py")))
    assert data["success"] is True
    assert "tests/test_unrelated.py" not in data["selected_tests"]


def test_selection_has_strategy(tmp_path):
    create_project(tmp_path)
    data = json.loads(select_tests_for_change(str(tmp_path), str(tmp_path / "app" / "brain.py")))
    assert data["success"] is True
    assert data["strategy"] in {"focused", "focused_then_full", "full_suite"}
