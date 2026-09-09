"""Unified execution pipeline for JARVIS."""

from __future__ import annotations

from threading import RLock
from pathlib import Path

from app.agent.events import EventType, get_event_bus
from app.agent.logging import get_logger
from app.agent.router import Router
from app.agent.session import Session
from app.memory.store import MemoryStore
from app.agent.orchestration import TaskLifecycle, TaskState


class AgentPipeline:
    """Central pipeline shared by all JARVIS interfaces."""

    def __init__(
        self,
        router: Router | None = None,
        session: Session | None = None,
    ):
        self.router = router or Router()
        self.session = session if session is not None else Session()
        self.memory = MemoryStore()

        self.events = get_event_bus()
        self.logger = get_logger()

        self._lock = RLock()
        self._busy = False
        self.current_task: TaskLifecycle | None = None

    @property
    def busy(self) -> bool:
        with self._lock:
            return self._busy

    def _execution_owner(self):
        """Return the Brain that owns this pipeline's production tool boundary."""
        brain = getattr(self.router, "brain", None)
        if brain is None or not hasattr(brain, "execution"):
            raise RuntimeError("This pipeline router does not provide an execution owner.")
        return brain

    @property
    def execution(self):
        """The single production ExecutionEngine used by this pipeline."""
        return self._execution_owner().execution

    @property
    def registry(self):
        return self._execution_owner().registry

    @property
    def security(self):
        return self._execution_owner().security

    # These are the application-core construction paths for optional systems.
    # They deliberately inject the existing Brain-owned boundary rather than
    # allowing a production caller to build a parallel one.
    def create_automation_engine(self, store, condition_check=None):
        from app.agent.automation import AutomationEngine
        return AutomationEngine(store, self.execution, condition_check)

    def create_workflow_engine(self, store):
        from app.agent.workflows import WorkflowEngine
        return WorkflowEngine(store, self.execution)

    def create_autonomous_task_manager(self):
        from app.agent.autonomous import AutonomousTaskManager
        return AutonomousTaskManager(self.execution)

    def create_coding_workflow(self, root: str | Path, *, dry_run: bool = False):
        from app.agent.coding import CodingWorkflow
        return CodingWorkflow(str(root), dry_run=dry_run, engine=self.execution, registry=self.registry)

    def create_workbench(self, root: str | Path, memory=None):
        from app.agent.workbench import EngineeringWorkbench
        return EngineeringWorkbench(str(root), self.execution, registry=self.registry, memory=memory)

    def create_executor(self):
        from app.agent.executor import Executor
        return Executor(brain=self._execution_owner())

    def process(
        self,
        user_text: str,
        on_response=None,
    ) -> str:
        """Process one user request."""

        user_text = user_text.strip()

        if not user_text:
            return ""

        with self._lock:
            if self._busy:
                return (
                    "I am still processing the previous request. "
                    "Humanity has not yet invented parallel brains."
                )

            self._busy = True

        try:
            self.current_task = TaskLifecycle()
            self.current_task.update(TaskState.THINKING, "routing request")
            self.logger.info("User request: %s", user_text)

            self.events.publish(
                EventType.TASK_STARTED,
                text=user_text,
                task_id=self.current_task.task_id,
                state=self.current_task.state.value,
            )

            self.events.publish(
                EventType.USER_TEXT,
                text=user_text,
            )

            # Preserve the conversation that existed BEFORE
            # this request. The current request is added only
            # after the router receives the previous context.
            context = self.session.as_messages()
            memories = self.memory.context(user_text, max_items=5, max_characters=1200)
            if memories:
                context.append({
                    "role": "system",
                    "content": "Relevant persistent memories:\n" + "\n".join(f"- {memory.content}" for memory in memories),
                })

            response = self.router.route(
                user_text,
                context=context,
            )
            self.current_task.update(TaskState.VERIFYING, "recording response")

            response = str(response).strip()

            if not response:
                response = (
                    "I completed the request but received "
                    "no response."
                )

            # Store both sides of the conversation.
            self.session.add_user(user_text)
            self.session.add_assistant(response)

            self.current_task.update(TaskState.COMPLETE)

            self.events.publish(
                EventType.RESPONSE,
                text=response,
            )

            self.events.publish(
                EventType.TASK_FINISHED,
                text=user_text,
                response=response,
                task_id=self.current_task.task_id,
                state=TaskState.COMPLETE.value,
                diagnostic=self.current_task.diagnostic(),
            )

            if on_response:
                on_response(response)

            self.logger.info(
                "JARVIS response: %s",
                response,
            )

            return response

        except Exception as exc:
            if self.current_task:
                self.current_task.update(TaskState.FAILED, error=str(exc))
            error = f"JARVIS pipeline error: {exc}"

            self.logger.exception(
                "Pipeline failure"
            )

            self.events.publish(
                EventType.ERROR,
                message=error,
            )

            self.events.publish(
                EventType.TASK_FAILED,
                text=user_text,
                error=str(exc),
                task_id=self.current_task.task_id if self.current_task else None,
            )

            return error

        finally:
            if self.current_task and self.current_task.state is not TaskState.FAILED:
                self.current_task.update(TaskState.COMPLETE)
            with self._lock:
                self._busy = False

    def clear_session(self) -> None:
        """Clear the shared conversation session."""

        self.session.clear()

        self.events.publish(
            EventType.RESPONSE,
            text="Conversation memory cleared.",
        )

        self.logger.info(
            "Conversation session cleared."
        )
