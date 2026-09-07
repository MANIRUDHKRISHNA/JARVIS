"""JARVIS request router."""
import json
import re
from pathlib import Path

from ollama import chat

from app.agent.brain import Brain
from app.agent.planner import Planner
from app.agent.executor import Executor
from app.agent.session import Session

from app.agent.security import PermissionLevel, SecurityManager

from app.tools.filesystem import (
    edit_file,
    read_file,
)


class Router:
    """Routes requests to the appropriate JARVIS workflow."""

    CODING_KEYWORDS = {
        "code",
        "coding",
        "program",
        "programming",
        "python",
        "javascript",
        "typescript",
        "bug",
        "debug",
        "debugging",
        "function",
        "class",
        "script",
        "project",
        "repository",
        "repo",
        "test",
        "pytest",
        "compile",
        "error",
        "exception",
        "implement",
        "refactor",
        "fix",
        "modify",
        "change",
        "edit",
        "open chrome",
        "browser",
        "website",
        "search the web",
        "spotify",
        "play music",
        "computer",
        "click",
        "type into",
        "navigate",
    }

    INSPECTION_KEYWORDS = {
        "inspect",
        "structure",
        "list",
        "show",
        "read",
        "find",
        "search",
        "where",
    }

    EDIT_KEYWORDS = {
        "change",
        "edit",
        "modify",
        "replace",
        "update",
        "fix",
        "alter",
    }

    def __init__(
        self,
        model: str = "qwen3:8b",
        confirm_callback=None,
        session=None,
    ):
        self.brain = Brain(
            model=model,
            confirm_callback=confirm_callback,
        )

        self.planner = Planner(
            model=model,
        )

        self.executor = Executor(
            brain=self.brain,
        )

        self.session = session if session is not None else Session()

    def handle(self, prompt: str) -> str:
        """Main router entry point."""

        return self.route(prompt)

    def route(self, prompt: str) -> str:
        text = prompt.strip()
        lower = text.lower()

        if not text:
            return "I need an actual request."

        self.session.add_user(text)

        # -----------------------------------------------------
        # Explicit existing-file edit
        # -----------------------------------------------------

        if self._looks_like_file_edit(text):
            path = self._extract_file_path(text)

            if path and Path(path).exists():
                return self._record_response(self._edit_existing_file(text, path))

        # -----------------------------------------------------
        # Explicit inspection
        # -----------------------------------------------------

        inspection_path = self._extract_inspection_path(text)

        if (
            inspection_path
            and any(
                keyword in lower
                for keyword in self.INSPECTION_KEYWORDS
            )
        ):
            return self._record_response(self.brain.think(self._with_context(text)))

        # -----------------------------------------------------
        # Complex coding task
        # -----------------------------------------------------

        words = set(
            re.findall(
                r"[a-zA-Z_]+",
                lower,
            )
        )

        if words & self.CODING_KEYWORDS:
            try:
                plan = self.planner.create_plan(text)

                return self._record_response(self.executor.execute(task=text, steps=plan))

            except Exception as exc:
                return self._record_response(
                    (
                    f"ERROR: Coding workflow failed: {exc}"
                    )
                )

        # -----------------------------------------------------
        # Normal assistant request
        # -----------------------------------------------------

        return self._record_response(self.brain.think(self._with_context(text)))

    def clear_session(self):
        """Clear short-term conversation context."""

        self.session.clear()

    def _with_context(self, request: str) -> str:
        history = self.session.context_text()

        if not history:
            return request

        return (
            "You are continuing an existing conversation.\n\n"
            f"CONVERSATION HISTORY:\n{history}\n\n"
            f"CURRENT REQUEST:\n{request}\n\n"
            "Use the history only when relevant and do not invent facts."
        )

    def _record_response(self, response: str) -> str:
        self.session.add_assistant(response)
        return response

    # ---------------------------------------------------------
    # Existing file editing
    # ---------------------------------------------------------

    def _edit_existing_file(
        self,
        prompt: str,
        path: str,
    ) -> str:
        """
        Deterministic existing-file edit workflow.

        read actual file -> ask model for precise edit ->
        validate old_text -> edit -> verify -> optionally test
        """

        actual = read_file(path)

        if actual.startswith("ERROR:"):
            return actual

        if not actual.strip():
            return (
                f"ERROR: The file is empty, so I cannot safely "
                f"perform a targeted edit: {path}"
            )

        edit_request = self._ask_for_edit(
            prompt,
            path,
            actual,
        )

        if edit_request is None:
            return (
                "ERROR: JARVIS could not determine a safe, "
                "exact edit from the current file contents."
            )

        old_text = edit_request.get("old_text", "")
        new_text = edit_request.get("new_text", "")

        if not old_text:
            return (
                "ERROR: The model did not provide the exact existing "
                "text to replace."
            )

        if old_text not in actual:
            return (
                "ERROR: The requested old_text does not exist in the "
                "actual file. The file was not changed."
            )

        occurrences = actual.count(old_text)

        if occurrences != 1:
            return (
                f"ERROR: The requested text occurs {occurrences} times "
                "in the file. The edit was refused because the target "
                "is not unique."
            )

        permission = SecurityManager().check_file_edit(path)

        if permission == PermissionLevel.BLOCK:
            return (
                f"BLOCKED: JARVIS will not edit this path: {path}"
            )

        if permission == PermissionLevel.CONFIRM:
            if not self.brain._request_confirmation(
                f"JARVIS wants to edit:\n\n{path}"
            ):
                return (
                    f"CANCELLED: User denied permission to edit {path}."
                )

        result = edit_file(
            path=path,
            old_text=old_text,
            new_text=new_text,
        )

        if not result.startswith("SUCCESS:"):
            return result

        # -----------------------------------------------------
        # Verify the actual final file
        # -----------------------------------------------------

        final_content = read_file(path)

        if final_content.startswith("ERROR:"):
            return (
                f"ERROR: Edit was reported successful, but the final "
                f"file could not be read: {path}"
            )

        if new_text not in final_content:
            return (
                "ERROR: Verification failed. The expected new text "
                "is not present in the final file."
            )

        # -----------------------------------------------------
        # Optional Python syntax/test verification
        # -----------------------------------------------------

        test_result = self._verify_python_file(path)

        if test_result:
            return (
                f"SUCCESS: Edited {path}.\n\n"
                f"Verification:\n{test_result}"
            )

        return (
            f"SUCCESS: Edited {path} and verified the new content."
        )

    def _ask_for_edit(
        self,
        prompt: str,
        path: str,
        actual: str,
    ):
        """
        Ask Qwen for an exact old_text/new_text pair based ONLY
        on the real file contents.
        """

        request = f"""
You are preparing ONE precise edit to an existing source file.

User request:
{prompt}

File:
{path}

CURRENT FILE CONTENTS:
<FILE>
{actual}
</FILE>

Return ONLY valid JSON in this exact format:

{{
  "old_text": "exact text copied from the current file",
  "new_text": "replacement text"
}}

Rules:

1. old_text MUST be copied exactly from CURRENT FILE CONTENTS.
2. Do not invent old_text.
3. old_text must include enough surrounding text to identify exactly
   one location.
4. Do not return Markdown.
5. Do not return code fences.
6. Do not return explanations.
7. Do not modify anything outside the requested change.
"""

        try:
            response = chat(
                model=self.brain.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an exact code-edit planning engine. "
                            "Return only valid JSON."
                        ),
                    },
                    {
                        "role": "user",
                        "content": request,
                    },
                ],
                think=False,
            )

            content = (
                response.message.content or ""
            ).strip()

            data = self._parse_json(content)

            if not isinstance(data, dict):
                return None

            if (
                "old_text" not in data
                or "new_text" not in data
            ):
                return None

            return {
                "old_text": str(
                    data["old_text"]
                ),
                "new_text": str(
                    data["new_text"]
                ),
            }

        except Exception:
            return None

    # ---------------------------------------------------------
    # Python verification
    # ---------------------------------------------------------

    def _verify_python_file(
        self,
        path: str,
    ) -> str:
        """Run a lightweight Python syntax check."""

        if not path.lower().endswith(".py"):
            return ""

        try:
            import subprocess

            result = subprocess.run(
                [
                    str(Path(self.brain.model and "python" or "python")),
                    "-m",
                    "py_compile",
                    path,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                return "Python syntax check passed."

            error = (
                result.stderr.strip()
                or result.stdout.strip()
                or "Unknown Python syntax error."
            )

            return (
                "Python syntax check FAILED:\n"
                + error
            )

        except Exception as exc:
            return (
                f"Could not run Python syntax verification: {exc}"
            )

    # ---------------------------------------------------------
    # Path extraction
    # ---------------------------------------------------------

    @staticmethod
    def _extract_file_path(
        text: str,
    ):
        """
        Extract a Windows absolute path without swallowing
        the rest of the sentence.
        """

        match = re.search(
            r"(?i)([a-z]:\\[^\s<>\"|?]+)",
            text,
        )

        if not match:
            return None

        path = match.group(1)

        return path.rstrip(
            ".,;:)]}"
        )

    def _extract_inspection_path(
        self,
        text: str,
    ):
        return self._extract_file_path(text)

    # ---------------------------------------------------------
    # Request classification
    # ---------------------------------------------------------

    def _looks_like_file_edit(
        self,
        text: str,
    ) -> bool:
        lower = text.lower()

        has_edit_word = any(
            word in lower
            for word in self.EDIT_KEYWORDS
        )

        has_path = bool(
            self._extract_file_path(text)
        )

        return has_edit_word and has_path

    # ---------------------------------------------------------
    # JSON helper
    # ---------------------------------------------------------

    @staticmethod
    def _parse_json(
        content: str,
    ):
        try:
            return json.loads(content)
        except Exception:
            pass

        fenced = re.search(
            r"```(?:json)?\s*(.*?)```",
            content,
            re.DOTALL | re.IGNORECASE,
        )

        if fenced:
            try:
                return json.loads(
                    fenced.group(1).strip()
                )
            except Exception:
                pass

        match = re.search(
            r"\{.*\}",
            content,
            re.DOTALL,
        )

        if match:
            try:
                return json.loads(
                    match.group(0)
                )
            except Exception:
                return None

        return None