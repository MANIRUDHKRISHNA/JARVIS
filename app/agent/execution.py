"""Bounded, evidence-first execution for the shared JARVIS agent core."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from threading import Event
from typing import Any, Callable

from app.agent.events import EventType, get_event_bus
from app.agent.results import ToolResult, normalize_tool_result


class StepStatus(str, Enum):
    PENDING = "pending"; READY = "ready"; RUNNING = "running"; SUCCEEDED = "succeeded"
    VERIFIED = "verified"; FAILED = "failed"; BLOCKED = "blocked"; RETRYING = "retrying"; CANCELLED = "cancelled"


@dataclass
class ExecutionLimits:
    max_steps: int = 12
    max_retries_per_step: int = 1
    max_execution_seconds: float = 120.0
    max_tool_calls: int = 20


@dataclass
class ExecutionStep:
    description: str
    tool: str
    arguments: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    verify: Callable[[ToolResult], bool] | None = None
    retryable: bool = False
    timeout_seconds: float | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: StepStatus = StepStatus.PENDING
    result: ToolResult | None = None
    retries: int = 0
    error: str | None = None
    started_at: float | None = None
    finished_at: float | None = None
    verification: bool | None = None


@dataclass
class ExecutionReport:
    task_id: str
    steps: list[ExecutionStep]
    started_at: float
    finished_at: float
    stopped_reason: str | None = None

    @property
    def success(self) -> bool:
        return bool(self.steps) and all(step.status is StepStatus.VERIFIED for step in self.steps)


class ExecutionEngine:
    """Executes explicit plans only; it never invents actions from prose."""

    def __init__(self, tool_executor, limits: ExecutionLimits | None = None, context_executor=None):
        self.tool_executor = tool_executor
        # Production registries can explicitly accept execution context.  The
        # base executor remains compatible with simple two-argument test fakes.
        self.context_executor = context_executor
        self.limits = limits or ExecutionLimits()
        self.cancel_event = Event()
        self.events = get_event_bus()

    def cancel(self) -> None:
        self.cancel_event.set()

    def execute(self, steps: list[ExecutionStep], task_id: str | None = None, *, confirmation_granted: bool = False) -> ExecutionReport:
        # perf_counter has the resolution required for short per-step timeout
        # enforcement on Windows; monotonic may be coarser on some hosts.
        started, task_id = time.perf_counter(), task_id or uuid.uuid4().hex
        reason = None
        if len(steps) > self.limits.max_steps:
            return ExecutionReport(task_id, steps, started, time.perf_counter(), "step budget exceeded")
        by_id = {step.id: step for step in steps}
        calls = 0
        while True:
            if self.cancel_event.is_set():
                reason = "cancelled"
                for step in steps:
                    if step.status in {StepStatus.PENDING, StepStatus.READY}:
                        step.status = StepStatus.CANCELLED
                break
            if time.perf_counter() - started > self.limits.max_execution_seconds:
                reason = "execution timeout"; break
            ready = [s for s in steps if s.status is StepStatus.PENDING and all(by_id.get(dep) and by_id[dep].status is StepStatus.VERIFIED for dep in s.dependencies)]
            for step in steps:
                if step.status is StepStatus.PENDING and any(by_id.get(dep) is None or by_id[dep].status in {StepStatus.FAILED, StepStatus.BLOCKED, StepStatus.CANCELLED} for dep in step.dependencies):
                    step.status, step.error = StepStatus.BLOCKED, "required dependency did not verify"
            if not ready:
                break
            for step in ready:
                if calls >= self.limits.max_tool_calls:
                    reason = "tool-call budget exceeded"; break
                step.status, step.started_at = StepStatus.RUNNING, time.perf_counter()
                self.events.publish(EventType.EXECUTION_PROGRESS, task_id=task_id, step_id=step.id, status=step.status.value)
                self.events.publish(EventType.TASK_STEP_STARTED, task_id=task_id, step_id=step.id, tool=step.tool)
                # Confirmation is execution context, never tool input.  Only
                # an explicitly configured context executor receives it.
                raw = (
                    self.context_executor(step.tool, step.arguments, confirmation_granted)
                    if self.context_executor is not None
                    else self.tool_executor(step.tool, step.arguments)
                )
                try: payload = json.loads(raw) if isinstance(raw, str) else raw
                except json.JSONDecodeError: payload = raw
                result = normalize_tool_result(step.tool, payload, step.arguments)
                calls += 1; step.result, step.finished_at = result, time.perf_counter()
                if step.timeout_seconds is not None and step.finished_at - step.started_at > step.timeout_seconds:
                    step.status, step.error = StepStatus.FAILED, "step timeout"
                    self.events.publish(EventType.EXECUTION_PROGRESS, task_id=task_id, step_id=step.id, status=step.status.value)
                    continue
                verified = result.verified if step.verify is None else bool(step.verify(result))
                step.verification = verified
                if result.success and verified:
                    step.status = StepStatus.VERIFIED
                elif result.success:
                    step.status, step.error = StepStatus.FAILED, "action completed but verification failed"
                elif result.error and result.error.lower().startswith(("blocked", "confirmation")):
                    step.status, step.error = StepStatus.BLOCKED, result.error
                elif step.retryable and step.retries < self.limits.max_retries_per_step:
                    step.retries += 1; step.status = StepStatus.PENDING
                else:
                    step.status, step.error = StepStatus.FAILED, result.error or result.message
                self.events.publish(EventType.EXECUTION_PROGRESS, task_id=task_id, step_id=step.id, status=step.status.value)
                self.events.publish(EventType.TASK_VERIFICATION, task_id=task_id, step_id=step.id, verified=bool(step.verification))
                if step.status is StepStatus.VERIFIED:
                    self.events.publish(EventType.TASK_STEP_COMPLETED, task_id=task_id, step_id=step.id)
            if reason: break
        return ExecutionReport(task_id, steps, started, time.perf_counter(), reason)
