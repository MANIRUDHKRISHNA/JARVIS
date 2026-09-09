from app.agent.coding import CodingState, CodingWorkflow
from app.agent.execution import ExecutionEngine


def test_edit_requires_inspection(tmp_path):
    target = tmp_path / "sample.py"
    target.write_text("value = 1\n", encoding="utf-8")
    workflow = CodingWorkflow(str(tmp_path))
    assert workflow.edit(str(target), "1", "2").startswith("ERROR:")
    assert "value = 1" in workflow.inspect(str(target))
    assert workflow.edit(str(target), "1", "2").startswith("SUCCESS:")
    assert target.read_text(encoding="utf-8") == "value = 2\n"


def test_dry_run_does_not_modify(tmp_path):
    target = tmp_path / "sample.py"
    target.write_text("value = 1\n", encoding="utf-8")
    workflow = CodingWorkflow(str(tmp_path), dry_run=True)
    workflow.inspect(str(target))
    assert workflow.edit(str(target), "1", "2").startswith("DRY RUN:")
    assert "1" in target.read_text(encoding="utf-8")


def test_context_report_records_actual_work(tmp_path):
    target = tmp_path / "sample.py"
    target.write_text("value = 1\n", encoding="utf-8")
    workflow = CodingWorkflow(str(tmp_path), dry_run=True)
    workflow.inspect(str(target))
    report = workflow.context.report()
    assert str(target.resolve()) in report["inspected"]
    assert report["modified"] == []


def test_workflow_uses_the_supplied_shared_execution_boundary(tmp_path):
    target = tmp_path / "sample.py"
    target.write_text("value = 1\n", encoding="utf-8")
    calls = []
    # A fake engine lets this test prove delegation without a live filesystem
    # mutation through the workflow's former direct helper call.
    engine = ExecutionEngine(lambda tool, args: calls.append(tool) or '{"success": true, "verified": true, "data": "content"}')
    workflow = CodingWorkflow(str(tmp_path), engine=engine)
    assert workflow.engine is engine
    assert workflow.registry is None
    assert workflow.inspect(str(target)) == "content"
    assert calls == ["read_file"]


def test_request_scoped_edit_lifecycle_returns_structured_verified_result(tmp_path):
    target = tmp_path / "sample.py"
    target.write_text("value = 1\n", encoding="utf-8")
    workflow = CodingWorkflow(str(tmp_path))

    result = workflow.run_edit_request("Update the value", str(target), "1", "2")

    assert result.status is CodingState.COMPLETED
    assert result.changed and result.verified
    assert str(target.resolve()) in result.files_inspected
    assert target.read_text(encoding="utf-8") == "value = 2\n"
    assert workflow.context.plan["task"] == "Update the value"


def test_request_states_are_isolated(tmp_path):
    first = CodingWorkflow(str(tmp_path), dry_run=True)
    second = CodingWorkflow(str(tmp_path), dry_run=True)
    first.context.state = CodingState.FAILED.value

    assert second.context.state == CodingState.IDLE.value


def test_preexisting_target_change_is_blocked_without_editing(tmp_path, monkeypatch):
    target = tmp_path / "sample.py"
    target.write_text("value = 1\n", encoding="utf-8")
    workflow = CodingWorkflow(str(tmp_path))
    relative = "sample.py"
    monkeypatch.setattr(workflow, "_snapshot", lambda: {"project": str(tmp_path), "files": [relative], "status": " M sample.py", "diff": "diff"})

    result = workflow.run_edit_request("Update", str(target), "1", "2")

    assert result.status is CodingState.BLOCKED
    assert "pre-existing" in result.failure_reason
    assert target.read_text(encoding="utf-8") == "value = 1\n"
