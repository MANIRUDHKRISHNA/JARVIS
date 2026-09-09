from app.agent.workbench import EngineeringWorkbench
from app.agent.execution import ExecutionEngine
import json


def test_workbench_snapshot_and_project_memory(tmp_path):
    (tmp_path / "sample.py").write_text("value = 1\n", encoding="utf-8")
    (tmp_path / "test_sample.py").write_text("def test_value():\n    assert True\n", encoding="utf-8")
    engine = ExecutionEngine(lambda tool, args: '{"success": true, "verified": true}')
    bench = EngineeringWorkbench(str(tmp_path), engine)
    snapshot = bench.snapshot()
    assert snapshot.root == str(tmp_path.resolve())
    assert "test_sample.py" in snapshot.tests
    assert bench.remember_decision("Tests must remain deterministic") is not None
    assert bench.workflow.engine is engine


def test_workbench_routes_diagnostics_and_tests_through_its_engine(tmp_path, monkeypatch):
    calls = []

    def dispatch(tool, arguments):
        calls.append((tool, arguments))
        return json.dumps({"success": True, "verified": True, "stdout": "ok", "stderr": ""})

    bench = EngineeringWorkbench(str(tmp_path), ExecutionEngine(dispatch))
    monkeypatch.setattr("app.agent.workbench.select_tests_for_change", lambda root, path: json.dumps({"selected_tests": ["test_sample.py"]}))

    bench.diagnose()
    bench.targeted_tests("sample.py")

    assert calls == [
        ("compile_project", {"project_path": str(tmp_path.resolve())}),
        ("run_tests", {"project_path": str(tmp_path.resolve()), "test_path": "test_sample.py"}),
    ]
