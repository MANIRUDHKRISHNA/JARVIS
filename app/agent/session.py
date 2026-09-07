"""Short-term conversation session management for JARVIS."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Message:
    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Session:
    """Maintain a bounded in-memory conversation context."""

    max_messages: int = 20
    messages: list[Message] = field(default_factory=list)

    def add_user(self, content: str):
        self.add("user", content)

    def add_assistant(self, content: str):
        self.add("assistant", content)

    def add(self, role: str, content: str):
        if not content or not content.strip():
            return
        self.messages.append(Message(role, content.strip()))
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

    def __len__(self):
        return len(self.messages)
