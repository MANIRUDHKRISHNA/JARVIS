from app.agent.orchestration import TaskLifecycle, TaskState


def test_task_lifecycle_has_safe_diagnostics():
    task = TaskLifecycle()
    task.update(TaskState.EXECUTING, "write file")
    data = task.diagnostic()
    assert data["state"] == "executing"
    assert data["current_step"] == "write file"
    assert "task_id" in data
