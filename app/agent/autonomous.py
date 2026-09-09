"""Bounded high-level task manager built on the authoritative execution engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from time import time
from typing import Any
from uuid import uuid4

from app.agent.events import EventType, get_event_bus
from app.agent.execution import ExecutionEngine, ExecutionReport, ExecutionStep, StepStatus


class AutonomousTaskState(str, Enum):
    REQUESTED = "requested"
    UNDERSTANDING = "understanding"
    PLANNING = "planning"
    WAITING_FOR_CONFIRMATION = "waiting_for_confirmation"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    RECOVERING = "recovering"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


@dataclass
class AutonomousTask:
    steps: list[ExecutionStep]
    session_id: str | None = None
    task_id: str = field(default_factory=lambda: uuid4().hex)
    state: AutonomousTaskState = AutonomousTaskState.REQUESTED
    created_at: float = field(default_factory=time)
    audit: list[dict[str, Any]] = field(default_factory=list)
    report: ExecutionReport | None = None

    def record(self, event: str, **data: Any) -> None:
        # Tool results may contain secrets; audit only state/identifiers/messages.
        self.audit.append({"timestamp": time(), "event": event, **{k: v for k, v in data.items() if "secret" not in k.lower() and "token" not in k.lower()}})


class AutonomousTaskManager:
    def __init__(self, engine: ExecutionEngine):
        self.engine = engine
        self.active: AutonomousTask | None = None
        self.events = get_event_bus()

    def create(self, steps: list[ExecutionStep], session_id: str | None = None) -> AutonomousTask:
        task = AutonomousTask(steps=steps, session_id=session_id)
        task.record("task_created")
        self.events.publish(EventType.TASK_STARTED, task_id=task.task_id, session_id=session_id)
        return task

    @staticmethod
    def _requires_confirmation(step: ExecutionStep) -> bool:
        return step.tool in {"delete_file", "remove_file", "shutdown", "restart", "git_reset", "git_push", "purchase", "send_message"} or bool(step.arguments.get("requires_confirmation"))

    def run(self, steps: list[ExecutionStep], session_id: str | None = None, confirmed: bool = False) -> ExecutionReport:
        task = self.create(steps, session_id)
        self.active = task
        task.state = AutonomousTaskState.PLANNING
        task.record("planning")
        self.events.publish(EventType.TASK_PLANNING, task_id=task.task_id)
        if any(self._requires_confirmation(step) for step in steps) and not confirmed:
            task.state = AutonomousTaskState.WAITING_FOR_CONFIRMATION
            task.record("confirmation_required")
            self.events.publish(EventType.TASK_CONFIRMATION_REQUIRED, task_id=task.task_id)
            return ExecutionReport(task.task_id, steps, time(), time(), "waiting for confirmation")
        task.state = AutonomousTaskState.EXECUTING
        task.report = self.engine.execute(steps, task.task_id)
        task.state = self._final_state(task.report)
        task.record("finished", state=task.state.value, stopped_reason=task.report.stopped_reason)
        event = EventType.TASK_FINISHED if task.state is AutonomousTaskState.COMPLETED else EventType.TASK_CANCELLED if task.state is AutonomousTaskState.CANCELLED else EventType.TASK_FAILED
        self.events.publish(event, task_id=task.task_id, state=task.state.value)
        return task.report

    def resume(self, confirmed: bool) -> ExecutionReport | None:
        if not self.active or self.active.state is not AutonomousTaskState.WAITING_FOR_CONFIRMATION:
            return None
        if not confirmed:
            return self.active.report
        task = self.active
        task.state = AutonomousTaskState.EXECUTING
        task.record("confirmation_received")
        task.report = self.engine.execute(task.steps, task.task_id)
        task.state = self._final_state(task.report)
        task.record("finished", state=task.state.value, stopped_reason=task.report.stopped_reason)
        event = EventType.TASK_FINISHED if task.state is AutonomousTaskState.COMPLETED else EventType.TASK_CANCELLED if task.state is AutonomousTaskState.CANCELLED else EventType.TASK_FAILED
        self.events.publish(event, task_id=task.task_id, state=task.state.value)
        return task.report

    @staticmethod
    def _final_state(report: ExecutionReport) -> AutonomousTaskState:
        if report.stopped_reason == "cancelled":
            return AutonomousTaskState.CANCELLED
        if any(step.status is StepStatus.BLOCKED for step in report.steps):
            return AutonomousTaskState.BLOCKED
        return AutonomousTaskState.COMPLETED if report.success else AutonomousTaskState.FAILED

    def final_report(self) -> dict[str, Any] | None:
        if not self.active:
            return None
        task = self.active
        outcome = "COMPLETED" if task.state is AutonomousTaskState.COMPLETED else "CANCELLED" if task.state is AutonomousTaskState.CANCELLED else "BLOCKED" if task.state is AutonomousTaskState.BLOCKED else "FAILED"
        if task.report and any(s.status is StepStatus.VERIFIED for s in task.report.steps) and outcome == "FAILED":
            outcome = "PARTIALLY COMPLETED"
        return {"status": outcome, "task_id": task.task_id, "session_id": task.session_id, "verified_steps": [s.id for s in (task.report.steps if task.report else []) if s.status is StepStatus.VERIFIED], "audit": task.audit}

    def cancel(self) -> None:
        self.engine.cancel()
        if self.active:
            self.active.record("cancel_requested")
