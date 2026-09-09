from app.agent.workbench import EngineeringWorkbench
from app.agent.execution import ExecutionEngine


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
