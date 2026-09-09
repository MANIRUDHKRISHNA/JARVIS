import json

from app.agent.autonomous import AutonomousTaskManager
from app.agent.execution import ExecutionEngine, ExecutionStep


def test_task_manager_reports_verified_execution():
    engine = ExecutionEngine(lambda tool, args: json.dumps({"success": True, "verified": True}))
    manager = AutonomousTaskManager(engine)
    assert manager.engine is engine
    report = manager.run([ExecutionStep("safe step", "read_file")])
    assert report.success
