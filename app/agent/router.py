"""Task routing for the JARVIS agent."""

from __future__ import annotations

import re
from pathlib import Path

from app.agent.brain import Brain
from app.agent.planner import Planner


class Router:
    """Routes user requests to the appropriate agent workflow."""

    COMPLEX_KEYWORDS = (
        "build",
        "create an application",
        "develop",
        "implement",
        "debug",
        "fix the bug",
        "refactor",
        "modify the project",
        "change the project",
        "write code",
        "coding",
        "test",
        "run tests",
    )

    INSPECTION_KEYWORDS = (
        "inspect",
        "analyze",
        "analyse",
        "look through",
        "explain this project",
        "understand this project",
        "what files",
        "show me the files",
        "read the",
    )

    def __init__(
        self,
        brain: Brain | None = None,
        planner: Planner | None = None,
    ):
        self.brain = brain or Brain()
        self.planner = planner or Planner()

    def route(
        self,
        user_text: str,
        context: list[dict[str, str]] | None = None,
    ) -> str:
        text = user_text.lower().strip()

        if self._is_inspection(text):
            return self.brain.think(
                user_text,
                context=context,
            )

        if self._is_explicit_file_operation(user_text):
            return self.brain.think(
                user_text,
                context=context,
            )

        if self._is_complex(text):
            plan = self.planner.create_plan(user_text)

            augmented = (
                f"User task:\n{user_text}\n\n"
                f"Suggested execution plan:\n{plan}\n\n"
                "Execute the task using the available tools. "
                "Do not claim success without verification."
            )

            return self.brain.think(
                augmented,
                context=context,
            )

        return self.brain.think(
            user_text,
            context=context,
        )

    def _is_complex(self, text: str) -> bool:
        return any(
            keyword in text
            for keyword in self.COMPLEX_KEYWORDS
        )

    def _is_inspection(self, text: str) -> bool:
        return any(
            keyword in text
            for keyword in self.INSPECTION_KEYWORDS
        )

    def _is_explicit_file_operation(self, text: str) -> bool:
        file_pattern = re.compile(
            r"(?i)([a-z]:\\[^\s<>\":|?*]+)"
        )

        has_path = bool(file_pattern.search(text))

        operations = (
            "edit",
            "modify",
            "change",
            "replace",
            "update",
            "write",
            "create",
            "delete",
            "remove",
        )

        return has_path and any(
            operation in text
            for operation in operations
        )