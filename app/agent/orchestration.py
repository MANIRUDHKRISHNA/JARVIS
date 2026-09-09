"""Task lifecycle observability for the one shared AgentPipeline."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum


class TaskState(str, Enum):
    IDLE = "idle"; THINKING = "thinking"; PLANNING = "planning"; EXECUTING = "executing"
    VERIFYING = "verifying"; WAITING_CONFIRMATION = "waiting_confirmation"; FAILED = "failed"; COMPLETE = "complete"


@dataclass
class TaskLifecycle:
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    state: TaskState = TaskState.IDLE
    started_at: float = field(default_factory=time.monotonic)
    current_step: str | None = None
    error: str | None = None

    @property
    def elapsed_seconds(self) -> float:
        return round(time.monotonic() - self.started_at, 3)

    def update(self, state: TaskState, step: str | None = None, error: str | None = None) -> None:
        self.state, self.current_step, self.error = state, step, error

    def diagnostic(self) -> dict:
        return {"task_id": self.task_id, "state": self.state.value, "current_step": self.current_step, "elapsed_seconds": self.elapsed_seconds, "error": self.error}
