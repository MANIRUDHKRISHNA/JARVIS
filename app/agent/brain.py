"""Core reasoning engine for the JARVIS agent."""

from __future__ import annotations

import json
import uuid
from typing import Any

from ollama import chat

from app.agent.events import EventType, get_event_bus
from app.agent.logging import get_logger
from app.agent.health import diagnose_runtime, record_crash
from app.agent.metrics import metrics
from app.agent.model_manager import ModelManager
from app.agent.security import (
    PermissionLevel,
    SecurityManager,
    check_command,
    check_file_edit,
    check_file_write,
)
from app.memory.store import MemoryStore

from app.tools.applications import open_application
from app.tools.browser import (
    browser_action,
    browser_search,
    open_browser,
    open_url,
)
from app.tools.code_index import (
    build_code_index,
    build_code_relationships,
    search_code_relationships,
    build_change_impact,
    select_tests_for_change,
    diagnose_test_failure,
)
from app.tools.computer import (
    computer_control,
    computer_health,
)
from app.tools.filesystem import (
    edit_file,
    list_directory,
    read_file,
    search_files,
    write_file,
)
from app.tools.git import (
    git_status,
    git_diff,
    git_diff_cached,
    git_log,
    git_branch,
    git_add,
    git_commit,
    git_push,
)
from app.tools.health import health_check
from app.tools.memory import (
    remember_memory,
    search_memory,
    list_memories,
    update_memory,
    forget_memory,
    clear_memory,
)
from app.tools.runtime import diagnose_runtime as diagnose_runtime_tool
from app.tools.knowledge import (
    index_file,
    index_directory,
    search_knowledge,
    semantic_search,
    get_document,
    remove_document,
    knowledge_status,
)
from app.tools.vision import (
    capture_screen,
    capture_active_window,
    analyze_image,
    verify_screen,
)
from app.tools.system import SystemTools
from app.tools.terminal import run_command
from app.tools.testing import run_tests


class Brain:
    """Qwen-backed reasoning and tool-execution engine."""

    MODEL = "qwen3:8b"
    MAX_TOOL_ITERATIONS = 8

    SYSTEM_PROMPT = """
You are JARVIS, a local personal AI assistant running on Windows.

You have real tools available to interact with the computer and project.

CRITICAL RULES:

1. NEVER pretend that you performed an action.
2. NEVER invent tool results.
3. NEVER claim a file was created unless the tool actually created it.
4. NEVER claim a test passed unless an actual test command passed.
5. NEVER claim Git changed unless Git actually reported the change.
6. Use tools whenever the user's request requires real computer access.
7. For coding tasks, inspect the relevant files before modifying them.
8. For existing files, use edit_file.
9. For new files, use write_file.
10. After code modifications, run appropriate tests or syntax checks.
11. If a test fails, diagnose the actual failure and attempt a repair.
12. Do not endlessly retry the same failed operation.
13. Never expose secrets, passwords, API keys, tokens, or private credentials.
14. Do not weaken Windows security.
15. Never disable antivirus, Defender, firewall, or security controls.
16. Destructive or security-sensitive operations require confirmation.
17. Git commit, push, reset, and checkpoint operations require confirmation.
18. Do not automatically commit or push unless explicitly requested.
19. When asked about the current conversation, use the supplied conversation context.
20. Treat previous assistant statements as context, not as proof that an action succeeded.
21. If a tool fails, report the actual failure.
22. Be concise unless detailed explanation is useful.

CODING WORKFLOW:

inspect -> locate -> read -> understand -> modify -> verify -> test -> report.

You are a real local agent, not a fictional assistant pretending to control the machine.
"""

    def __init__(
        self,
        model: str | None = None,
        security: SecurityManager | None = None,
        memory: MemoryStore | None = None,
        confirm_callback=None,
    ):
        self.name = "JARVIS"
        self.model = model or self.MODEL

        self.security = (
            security
            if security is not None
            else SecurityManager()
        )

        self.memory = (
            memory
            if memory is not None
            else MemoryStore()
        )

        self.confirm_callback = confirm_callback

        self.events = get_event_bus()
        self.logger = get_logger()
        self.model_manager = ModelManager()

        self.system_tools = SystemTools()

        self.tools = [
            open_application,
            run_command,
            list_directory,
            search_files,
            read_file,
            write_file,
            edit_file,
            run_tests,

            build_code_index,
            build_code_relationships,
            search_code_relationships,
            build_change_impact,
            select_tests_for_change,
            diagnose_test_failure,

            git_status,
            git_diff,
            git_diff_cached,
            git_log,
            git_branch,
            git_add,
            git_commit,
            git_push,

            health_check,
            remember_memory,
            search_memory,
            list_memories,
            update_memory,
            forget_memory,
            clear_memory,
            diagnose_runtime_tool,
            index_file,
            index_directory,
            search_knowledge,
            semantic_search,
            get_document,
            remove_document,
            knowledge_status,
            capture_screen,
            capture_active_window,
            analyze_image,
            verify_screen,

            computer_control,
            computer_health,

            open_browser,
            open_url,
            browser_search,
            browser_action,
        ]

        self.tool_map = {
            tool.__name__: tool
            for tool in self.tools
        }

    def think(
        self,
        user_text: str,
        context: list[dict[str, str]] | None = None,
    ) -> str:
        """Reason about a request and execute required tools."""

        request_id = str(uuid.uuid4())
        metrics.start_response(request_id)
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": self.SYSTEM_PROMPT,
            }
        ]

        if context:
            messages.extend(context)

        messages.append(
            {
                "role": "user",
                "content": user_text,
            }
        )

        self.events.publish(
            EventType.THINKING_START,
            text=user_text,
        )

        try:
            for _ in range(self.MAX_TOOL_ITERATIONS):
                response = self._chat_with_recovery(messages)

                message = response.message

                tool_calls = getattr(
                    message,
                    "tool_calls",
                    None,
                )

                if tool_calls:
                    messages.append(
                        {
                            "role": "assistant",
                            "content": getattr(
                                message,
                                "content",
                                "",
                            ),
                            "tool_calls": tool_calls,
                        }
                    )

                    for call in tool_calls:
                        name = call.function.name
                        arguments = (
                            call.function.arguments or {}
                        )

                        result = self._execute_tool(
                            name,
                            arguments,
                        )

                        messages.append(
                            {
                                "role": "tool",
                                "content": result,
                            }
                        )

                    continue

                content = getattr(
                    message,
                    "content",
                    "",
                )

                if content:
                    return str(content).strip()

                return (
                    "I completed the request but received "
                    "no textual response."
                )

            return (
                "I stopped because the tool execution limit "
                "was reached. I will not keep repeating the "
                "same operations indefinitely."
            )

        except Exception as exc:
            self.logger.exception(
                "Brain failure"
            )

            self.events.publish(
                EventType.ERROR,
                message=str(exc),
            )

            record_crash(str(exc), gpu=diagnose_runtime(self.model_manager).get("gpu"))

            return f"I encountered an error: {exc}"

        finally:
            metrics.finish_response(request_id)
            self.events.publish(
                EventType.THINKING_END,
            )

    def _execute_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> str:
        """Execute one tool after applying safety checks."""

        tool = self.tool_map.get(name)

        if tool is None:
            return json.dumps(
                {
                    "success": False,
                    "error": f"Unknown tool: {name}",
                }
            )

        permission = self._permission(
            name,
            arguments,
        )

        # Git operations have dedicated security checks.
        #
        # This keeps the Brain aligned with the public
        # SecurityManager API used by the Git tests.
        if name == "git_add":
            permission = self.security.check_git_add()

        elif name == "git_commit":
            permission = self.security.check_git_commit()

        elif name == "git_push":
            permission = self.security.check_git_push()

        # Handle explicit user confirmation.
        if (
            permission == PermissionLevel.CONFIRM
            and name in {
                "git_add",
                "git_commit",
                "git_push",
            }
            and self.confirm_callback is not None
        ):
            try:
                confirmed = bool(
                    self.confirm_callback(
                        f"Confirm Git operation: {name}"
                    )
                )

            except Exception:
                self.logger.exception(
                    "Git confirmation callback failed."
                )

                return (
                    "BLOCKED: Confirmation callback failed."
                )

            if not confirmed:
                return (
                    "CANCELLED: User denied confirmation."
                )

            permission = PermissionLevel.SAFE

        if permission == PermissionLevel.BLOCK:
            return (
                "BLOCKED: Operation blocked by JARVIS "
                "security policy."
            )

        if permission == PermissionLevel.CONFIRM:
            return (
                "CONFIRMATION REQUIRED: This operation "
                "requires user confirmation before execution."
            )

        self.events.publish(
            EventType.TOOL_START,
            tool=name,
            arguments=arguments,
        )

        self.logger.info(
            "Executing tool %s with %s",
            name,
            arguments,
        )

        try:
            result = tool(**arguments)

            if isinstance(result, str):
                output = result

            else:
                output = json.dumps(
                    result,
                    ensure_ascii=False,
                    default=str,
                )

            self.events.publish(
                EventType.TOOL_END,
                tool=name,
                success=True,
            )

            return output

        except Exception as exc:
            self.logger.exception(
                "Tool %s failed",
                name,
            )

            self.events.publish(
                EventType.TOOL_END,
                tool=name,
                success=False,
                error=str(exc),
            )

            return json.dumps(
                {
                    "success": False,
                    "tool": name,
                    "error": str(exc),
                }
            )

    def _chat_with_recovery(self, messages):
        """Retry one model request only after recording a real failure."""

        try:
            return chat(model=self.model, messages=messages, tools=self.tools, think=False)
        except Exception as exc:
            diagnostics = diagnose_runtime(self.model_manager)
            record_crash(str(exc), gpu=diagnostics.get("gpu"), ram=diagnostics.get("ram"))
            self.logger.exception("Model request failed")
            if self.model_manager.command and self.model_manager.restart():
                self.events.publish(EventType.ERROR, message="Model failure detected; recovery attempted.")
                return chat(model=self.model, messages=messages, tools=self.tools, think=False)
            raise

    def _permission(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> PermissionLevel:
        """Determine whether a tool operation is allowed."""

        if name == "run_command":
            command = arguments.get(
                "command",
                "",
            )

            return check_command(
                command,
                self.security,
            )

        if name == "write_file":
            path = arguments.get(
                "path",
                "",
            )

            return check_file_write(
                path,
                self.security,
            )

        if name == "edit_file":
            path = arguments.get(
                "path",
                "",
            )

            return check_file_edit(
                path,
                self.security,
            )

        if name in {
            "git_add",
            "git_commit",
            "git_push",
        }:
            if name == "git_add":
                return self.security.check_git_add()

            if name == "git_commit":
                return self.security.check_git_commit()

            return self.security.check_git_push()

        if name in {
            "computer_control",
            "browser_action",
        }:
            action = str(
                arguments.get(
                    "instruction",
                    arguments.get(
                        "action",
                        "",
                    ),
                )
            )

            return self.security.check_computer_control(
                action
            )

        return PermissionLevel.SAFE