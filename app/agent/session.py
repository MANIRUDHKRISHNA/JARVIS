"""Short-term conversation session management for JARVIS."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Message:
    role: str
    content: str


@dataclass
class Session:
    """Maintain a bounded in-memory conversation context."""

    max_messages: int = 20
    messages: list[Message] = field(default_factory=list)

    def add_user(self, content: str):
        self.messages.append(Message("user", content))
        self._trim()

    def add_assistant(self, content: str):
        self.messages.append(Message("assistant", content))
        self._trim()

    def clear(self):
        self.messages.clear()

    def _trim(self):
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]

    def as_messages(self):
        return [{"role": message.role, "content": message.content} for message in self.messages]

    def context_text(self) -> str:
        return "\n".join(f"{message.role.upper()}: {message.content}" for message in self.messages)
