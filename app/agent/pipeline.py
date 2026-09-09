"""Unified execution pipeline for JARVIS."""

from __future__ import annotations

from threading import RLock

from app.agent.events import EventType, get_event_bus
from app.agent.logging import get_logger
from app.agent.router import Router
from app.agent.session import Session
from app.memory.store import MemoryStore


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

    @property
    def busy(self) -> bool:
        with self._lock:
            return self._busy

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
            self.logger.info("User request: %s", user_text)

            self.events.publish(
                EventType.TASK_STARTED,
                text=user_text,
            )

            self.events.publish(
                EventType.USER_TEXT,
                text=user_text,
            )

            # Preserve the conversation that existed BEFORE
            # this request. The current request is added only
            # after the router receives the previous context.
            context = self.session.as_messages()
            memories = self.memory.search(user_text, limit=5)
            if memories:
                context.append({
                    "role": "system",
                    "content": "Relevant persistent memories:\n" + "\n".join(f"- {memory.content}" for memory in memories),
                })

            response = self.router.route(
                user_text,
                context=context,
            )

            response = str(response).strip()

            if not response:
                response = (
                    "I completed the request but received "
                    "no response."
                )

            # Store both sides of the conversation.
            self.session.add_user(user_text)
            self.session.add_assistant(response)

            self.events.publish(
                EventType.RESPONSE,
                text=response,
            )

            self.events.publish(
                EventType.TASK_FINISHED,
                text=user_text,
                response=response,
            )

            if on_response:
                on_response(response)

            self.logger.info(
                "JARVIS response: %s",
                response,
            )

            return response

        except Exception as exc:
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
            )

            return error

        finally:
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