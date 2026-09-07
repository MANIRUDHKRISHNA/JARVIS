"""Conversation session management for JARVIS."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class Message:
    """One message in the conversation."""

    role: str
    content: str
    timestamp: str


class Session:
    """Bounded conversation history shared by all JARVIS interfaces."""

    def __init__(self, max_messages: int = 20):
        self.max_messages = max(2, max_messages)
        self.messages: list[Message] = []

    def add(self, role: str, content: str) -> None:
        """Add a message to the conversation."""
        if not content:
            return

        self.messages.append(
            Message(
                role=role,
                content=content,
                timestamp=datetime.now().isoformat(timespec="seconds"),
            )
        )

        self.trim()

    def add_user(self, content: str) -> None:
        self.add("user", content)

    def add_assistant(self, content: str) -> None:
        self.add("assistant", content)

    def trim(self) -> None:
        """Keep only the most recent messages."""
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages :]

    def as_messages(self) -> list[dict[str, str]]:
        """Return history in Ollama-compatible message format."""
        return [
            {
                "role": message.role,
                "content": message.content,
            }
            for message in self.messages
        ]

    def context_text(self) -> str:
        """Return readable conversation context."""
        if not self.messages:
            return ""

        lines = []

        for message in self.messages:
            speaker = "User" if message.role == "user" else "JARVIS"
            lines.append(f"{speaker}: {message.content}")

        return "\n".join(lines)

    def clear(self) -> None:
        """Clear the current conversation."""
        self.messages.clear()

    def __len__(self) -> int:
        return len(self.messages)
