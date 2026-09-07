"""Unified JARVIS agent pipeline."""

from __future__ import annotations

import time
from typing import Callable

from app.agent.events import EventType, get_event_bus
from app.agent.logging import logger
from app.agent.router import Router
from app.agent.session import Session


class AgentPipeline:
    """Coordinate user input, routing, session state, and events."""

    def __init__(self, router: Router | None = None, session: Session | None = None):
        self.session = session or Session()
        self.router = router or Router(session=self.session)
        self.events = get_event_bus()
        self._busy = False

    @property
    def busy(self) -> bool:
        return self._busy

    def process(self, user_text: str, on_response: Callable[[str], None] | None = None) -> str:
        user_text = user_text.strip()
        if not user_text:
            return ""
        if self._busy:
            return "I am already processing another request."
        self._busy = True
        started = time.perf_counter()
        self.events.publish(EventType.USER_TEXT, text=user_text)
        router_uses_session = getattr(self.router, "session", None) is self.session
        if not router_uses_session:
            self.session.add_user(user_text)
        self.events.publish(EventType.THINKING_START, text=user_text)
        logger.info("Processing user request: %s", user_text)
        try:
            response = str(self.router.route(user_text) or "").strip()
            if not router_uses_session:
                self.session.add_assistant(response)
            self.events.publish(EventType.RESPONSE, text=response)
            if on_response:
                on_response(response)
            logger.info("Request completed in %.2fs", time.perf_counter() - started)
            return response
        except Exception as exc:
            logger.exception("Agent pipeline failure")
            self.events.publish(EventType.ERROR, error=str(exc))
            return f"I could not complete that request. The actual error was: {exc}"
        finally:
            self.events.publish(EventType.THINKING_END)
            self._busy = False
