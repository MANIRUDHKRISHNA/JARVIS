"""Unified execution pipeline for JARVIS."""

from __future__ import annotations

from pathlib import Path
from threading import RLock
from typing import Callable

from app.agent.events import EventType, get_event_bus
from app.agent.logging import get_logger
from app.agent.orchestration import (
    TaskLifecycle,
    TaskState,
)
from app.agent.router import Router
from app.agent.session import Session
from app.memory.store import MemoryStore


YES_RESPONSES = {
    "yes",
    "y",
    "yeah",
    "yep",
    "yup",
    "ok",
    "okay",
    "approve",
    "approved",
    "confirm",
    "confirmed",
    "do it",
    "go ahead",
    "proceed",
    "continue",
}


NO_RESPONSES = {
    "no",
    "n",
    "nope",
    "cancel",
    "cancel it",
    "deny",
    "denied",
    "stop",
    "don't",
    "dont",
    "abort",
}


class AgentPipeline:
    """Single shared pipeline for UI and voice requests."""

    def __init__(
        self,
        router: Router | None = None,
        session: Session | None = None,
    ):
        self.router = (
            router
            if router is not None
            else Router()
        )

        self.session = (
            session
            if session is not None
            else Session()
        )

        self.memory = MemoryStore()

        self.events = get_event_bus()
        self.logger = get_logger()

        self._lock = RLock()
        self._busy = False
        self.current_task: TaskLifecycle | None = None

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    @property
    def busy(self) -> bool:
        with self._lock:
            return self._busy

    # ------------------------------------------------------------------
    # Authoritative execution boundary
    # ------------------------------------------------------------------

    def _execution_owner(self):
        """
        Return the Brain owned by this pipeline's Router.

        The pipeline must never create a second ExecutionEngine,
        ToolRegistry or SecurityManager.
        """

        brain = getattr(
            self.router,
            "brain",
            None,
        )

        if brain is None:
            raise RuntimeError(
                "Router does not expose its Brain."
            )

        if not hasattr(brain, "execution"):
            raise RuntimeError(
                "Router Brain does not expose an execution engine."
            )

        if not hasattr(brain, "registry"):
            raise RuntimeError(
                "Router Brain does not expose a tool registry."
            )

        return brain

    @property
    def execution(self):
        """Return the single Brain-owned execution engine."""

        return self._execution_owner().execution

    @property
    def registry(self):
        """Return the single Brain-owned tool registry."""

        return self._execution_owner().registry

    @property
    def security(self):
        """Return the single Brain-owned security manager."""

        return self._execution_owner().security

    # ------------------------------------------------------------------
    # Confirmation handling
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_confirmation(
        text: str,
    ) -> str:
        return " ".join(
            text.strip().lower().split()
        )

    def _handle_pending_confirmation(
        self,
        user_text: str,
    ) -> str | None:
        """
        Resolve pending confirmation before Router/Qwen sees the text.

        Returns:
            str:
                A pending confirmation was handled.

            None:
                No confirmation was pending.
        """

        brain = self._execution_owner()

        pending = brain.get_pending_confirmation()

        if pending is None:
            return None

        text = self._normalise_confirmation(
            user_text
        )

        if text in YES_RESPONSES:
            return brain.confirm_pending_confirmation()

        if text in NO_RESPONSES:
            return brain.cancel_pending_confirmation()

        return (
            "I am waiting for confirmation for this operation:\n"
            f"{pending.description}\n\n"
            "Reply 'yes' to proceed or 'no' to cancel."
        )

    # ------------------------------------------------------------------
    # Main request path
    # ------------------------------------------------------------------

    def process(
        self,
        user_text: str,
        on_response: Callable[[str], None] | None = None,
    ) -> str:
        """Process one request through the shared JARVIS pipeline."""

        user_text = (
            user_text or ""
        ).strip()

        if not user_text:
            return ""

        # --------------------------------------------------------------
        # Confirmation MUST happen before the busy check.
        # --------------------------------------------------------------

        with self._lock:
            confirmation_response = (
                self._handle_pending_confirmation(
                    user_text
                )
            )

            if confirmation_response is not None:
                self.session.add_user(
                    user_text
                )

                self.session.add_assistant(
                    confirmation_response
                )

                self.events.publish(
                    EventType.RESPONSE,
                    text=confirmation_response,
                )

                if on_response:
                    on_response(
                        confirmation_response
                    )

                return confirmation_response

            if self._busy:
                return (
                    "I am still processing the previous request."
                )

            self._busy = True

        task_failed = False

        try:
            # ----------------------------------------------------------
            # Create lifecycle
            # ----------------------------------------------------------

            self.current_task = TaskLifecycle()

            self.current_task.update(
                TaskState.THINKING,
                "routing request",
            )

            task_id = (
                self.current_task.task_id
            )

            self.logger.info(
                "User request: %s",
                user_text,
            )

            self.events.publish(
                EventType.TASK_STARTED,
                text=user_text,
                task_id=task_id,
                state=self.current_task.state.value,
            )

            self.events.publish(
                EventType.USER_TEXT,
                text=user_text,
            )

            # ----------------------------------------------------------
            # Conversation context
            # ----------------------------------------------------------

            context = self.session.as_messages()

            try:
                memories = self.memory.context(
                    user_text,
                    max_items=5,
                    max_characters=1200,
                )

                if memories:
                    memory_text = "\n".join(
                        f"- {memory.content}"
                        for memory in memories
                    )

                    context.append(
                        {
                            "role": "system",
                            "content": (
                                "Relevant persistent memories:\n"
                                f"{memory_text}"
                            ),
                        }
                    )

            except Exception:
                self.logger.exception(
                    "Memory context lookup failed"
                )

            # ----------------------------------------------------------
            # Routing
            # ----------------------------------------------------------

            self.current_task.update(
                TaskState.THINKING,
                "routing request",
            )

            response = self.router.route(
                user_text,
                context=context,
            )

            response = str(
                response or ""
            ).strip()

            # ----------------------------------------------------------
            # Confirmation may now exist because Brain encountered a
            # protected operation.
            # ----------------------------------------------------------

            if self._execution_owner().has_pending_confirmation():
                self.current_task.update(
                    TaskState.WAITING_CONFIRMATION,
                    "waiting for user confirmation",
                )

                self.session.add_user(
                    user_text
                )

                self.session.add_assistant(
                    response
                )

                self.events.publish(
                    EventType.TASK_CONFIRMATION_REQUIRED,
                    task_id=task_id,
                    request_id=task_id,
                    response=response,
                )

                self.events.publish(
                    EventType.RESPONSE,
                    text=response,
                )

                if on_response:
                    on_response(response)

                return response

            # ----------------------------------------------------------
            # Normal completion
            # ----------------------------------------------------------

            if not response:
                response = (
                    "I completed the request but "
                    "received no response."
                )

            self.current_task.update(
                TaskState.VERIFYING,
                "recording response",
            )

            self.session.add_user(
                user_text
            )

            self.session.add_assistant(
                response
            )

            self.current_task.update(
                TaskState.COMPLETE
            )

            self.events.publish(
                EventType.RESPONSE,
                text=response,
            )

            self.events.publish(
                EventType.TASK_FINISHED,
                text=user_text,
                response=response,
                task_id=task_id,
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
            task_failed = True

            if self.current_task:
                self.current_task.update(
                    TaskState.FAILED,
                    error=str(exc),
                )

            error = (
                f"JARVIS pipeline error: {exc}"
            )

            self.logger.exception(
                "Pipeline failure"
            )

            task_id = (
                self.current_task.task_id
                if self.current_task
                else None
            )

            self.events.publish(
                EventType.ERROR,
                task_id=task_id,
                message=error,
            )

            self.events.publish(
                EventType.TASK_FAILED,
                text=user_text,
                error=str(exc),
                task_id=task_id,
            )

            return error

        finally:
            # Do not turn WAITING_CONFIRMATION into COMPLETE.
            if (
                self.current_task
                and not task_failed
                and self.current_task.state
                not in {
                    TaskState.WAITING_CONFIRMATION,
                    TaskState.COMPLETE,
                }
            ):
                self.current_task.update(
                    TaskState.COMPLETE
                )

            with self._lock:
                self._busy = False

    # ------------------------------------------------------------------
    # Session
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Optional subsystem factories
    # ------------------------------------------------------------------

    def create_automation_engine(
        self,
        store,
        condition_check=None,
    ):
        from app.agent.automation import AutomationEngine

        return AutomationEngine(
            store,
            self.execution,
            condition_check,
        )

    def create_workflow_engine(
        self,
        store,
    ):
        from app.agent.workflows import WorkflowEngine

        return WorkflowEngine(
            store,
            self.execution,
        )

    def create_autonomous_task_manager(self):
        from app.agent.autonomous import (
            AutonomousTaskManager,
        )

        return AutonomousTaskManager(
            self.execution
        )

    def create_coding_workflow(
        self,
        root: str | Path,
        *,
        dry_run: bool = False,
    ):
        return self._execution_owner().create_coding_workflow(
            str(root),
            dry_run=dry_run,
        )

    def create_workbench(
        self,
        root: str | Path,
        memory=None,
    ):
        from app.agent.workbench import EngineeringWorkbench

        return EngineeringWorkbench(
            str(root),
            self.execution,
            registry=self.registry,
            memory=memory,
        )

    def create_executor(self):
        from app.agent.executor import Executor

        return Executor(
            brain=self._execution_owner()
        )


__all__ = [
    "AgentPipeline",
    "YES_RESPONSES",
    "NO_RESPONSES",
]