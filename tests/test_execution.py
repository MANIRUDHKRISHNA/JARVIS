import json
import time

from app.agent.execution import ExecutionEngine, ExecutionLimits, ExecutionStep, StepStatus


def result(success=True, verified=True, error=None):
    return json.dumps({"success": success, "verified": verified, "error": error})


def test_dependency_plan_executes_in_order():
    calls = []
    engine = ExecutionEngine(lambda tool, args: calls.append(tool) or result())
    first = ExecutionStep("create", "write_file")
    second = ExecutionStep("verify", "read_file", dependencies=[first.id])
    report = engine.execute([first, second])
    assert report.success and calls == ["write_file", "read_file"]


def test_unverified_action_fails_without_fake_success():
    engine = ExecutionEngine(lambda tool, args: result(True, False))
    step = ExecutionStep("launch", "open_application")
    report = engine.execute([step])
    assert not report.success and step.status is StepStatus.FAILED


def test_explicit_context_executor_receives_confirmation_without_tool_arguments():
    calls = []

    def context_executor(tool, arguments, confirmation_granted):
        calls.append((tool, arguments, confirmation_granted))
        return result(True, True)

    engine = ExecutionEngine(lambda tool, args: result(), context_executor=context_executor)
    report = engine.execute([ExecutionStep("confirm", "git_add", {"paths": ["x"]})], confirmation_granted=True)

    assert report.success
    assert calls == [("git_add", {"paths": ["x"]}, True)]


def test_budget_prevents_duplicate_execution():
    engine = ExecutionEngine(lambda tool, args: result(), ExecutionLimits(max_steps=1))
    steps = [ExecutionStep("one", "x"), ExecutionStep("two", "y")]
    report = engine.execute(steps)
    assert report.stopped_reason == "step budget exceeded"


def test_step_timeout_is_reported():
    def slow(tool, args):
        time.sleep(0.01)
        return result()
    step = ExecutionStep("slow", "x", timeout_seconds=0.001)
    report = ExecutionEngine(slow).execute([step])
    assert not report.success and step.error == "step timeout"
