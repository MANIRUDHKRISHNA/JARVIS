"""Core reasoning engine for the JARVIS agent."""

from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable

from ollama import chat

from app.agent.capabilities import (
    RiskLevel,
    ToolMetadata,
    ToolRegistry,
)
from app.agent.events import EventType, get_event_bus
from app.agent.execution import (
    ExecutionEngine,
    ExecutionLimits,
    ExecutionStep,
)
from app.agent.health import diagnose_runtime, record_crash
from app.agent.logging import get_logger
from app.agent.metrics import metrics
from app.agent.model_manager import ModelManager
from app.agent.results import normalize_tool_result
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
    build_change_impact,
    build_code_index,
    build_code_relationships,
    diagnose_test_failure,
    search_code_relationships,
    select_tests_for_change,
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
    git_add,
    git_branch,
    git_commit,
    git_diff,
    git_diff_cached,
    git_log,
    git_push,
    git_status,
)
from app.tools.health import health_check
from app.tools.knowledge import (
    get_document,
    index_directory,
    index_file,
    knowledge_status,
    remove_document,
    search_knowledge,
    semantic_search,
)
from app.tools.memory import (
    clear_memory,
    forget_memory,
    list_memories,
    remember_memory,
    search_memory,
    update_memory,
)
from app.tools.spotify import (
    spotify_next,
    spotify_pause,
    spotify_play,
    spotify_previous,
    spotify_resume,
    spotify_status,
)
from app.tools.runtime import diagnose_runtime as diagnose_runtime_tool
from app.tools.testing import compile_project, run_tests
from app.tools.terminal import run_command
from app.tools.vision import (
    analyze_image,
    capture_active_window,
    capture_screen,
    verify_screen,
)


MAX_TOOL_ITERATIONS = 8
CONFIRMATION_TIMEOUT_SECONDS = 300


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


@dataclass
class PendingConfirmation:
    """Exact operation waiting for explicit user approval."""

    confirmation_id: str
    request_id: str
    tool_name: str
    arguments: dict[str, Any]
    description: str
    created_at: float

    @property
    def expired(self) -> bool:
        return (
            time.monotonic() - self.created_at
            > CONFIRMATION_TIMEOUT_SECONDS
        )


class ConfirmationRequired(Exception):
    """Internal signal used to stop model reasoning immediately."""

    def __init__(
        self,
        confirmation: PendingConfirmation,
    ):
        self.confirmation = confirmation
        super().__init__(confirmation.description)


class Brain:
    """Reasoning layer with strict security and bounded tool execution."""

    MODEL = "qwen3:8b"

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
7. For coding tasks, inspect relevant files before modifying them.
8. For existing files, use edit_file.
9. For new files, use write_file.
10. After code modifications, run appropriate tests or syntax checks.
11. If a test fails, diagnose the actual failure.
12. Do not endlessly retry the same failed operation.
13. Never expose secrets, passwords, API keys, tokens, or private credentials.
14. Do not weaken Windows security.
15. Never disable antivirus, Defender, firewall, or security controls.
16. Destructive or security-sensitive operations require confirmation.
17. Git commit, push, reset, checkout, clean, add, and repository mutations
    require confirmation when the security layer says so.
18. Do not automatically approve a confirmation request.
19. Never interpret unrelated text as approval.
20. If a tool fails, report the actual failure.
21. Keep tool calls precise and use the minimum required arguments.
22. Do not repeatedly call a tool after confirmation is required.
23. For externally verifiable factual questions, use browser_search before
    answering when the information may be uncertain, current, specific,
    person-related, entertainment-related, historical, numerical, or
    otherwise easy to verify online.

24. Questions involving "who played", "who is", "when did", "where is",
    "latest", "current", "today", "news", "price", "score", "release",
    "version", "verify", "fact check", or similar factual requests should
    normally use browser_search.

25. When browser_search returns evidence, use that evidence as the basis
    for the answer instead of relying on model memory.

26. Never contradict verified search evidence using unsupported memory.

27. If browser_search fails or returns NO_RESULTS, explicitly state that
    the information could not be verified. Do not invent an answer.

CODING WORKFLOW:

inspect -> locate -> read -> understand -> modify -> verify -> test -> report.

You are a real local agent, not a fictional assistant pretending to control
the machine.
"""

    def __init__(
        self,
        model: str | None = None,
        security: SecurityManager | None = None,
        memory: MemoryStore | None = None,
        model_manager: ModelManager | None = None,
        confirm_callback: Callable[[str], bool] | None = None,
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

        self.model_manager = (
            model_manager
            if model_manager is not None
            else ModelManager()
        )

        self._confirmation_lock = threading.RLock()
        self._pending_confirmation: PendingConfirmation | None = None

        self.tools = [
            open_application,
            spotify_status,
            spotify_play,
            spotify_pause,
            spotify_resume,
            spotify_next,
            spotify_previous,

            run_command,

            list_directory,
            search_files,
            read_file,
            write_file,
            edit_file,

            run_tests,
            compile_project,

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

        self.registry = ToolRegistry(self.security)

        self._register_tools()

        self.execution = ExecutionEngine(
            self.registry.dispatch,
            ExecutionLimits(
                max_steps=1,
                max_tool_calls=1,
                max_retries_per_step=0,
            ),
            context_executor=(
                lambda tool, arguments, granted:
                self.registry.dispatch(
                    tool,
                    arguments,
                    confirmation_granted=granted,
                )
            ),
        )

    # ------------------------------------------------------------------
    # Tool registration
    # ------------------------------------------------------------------

    def _register_tools(self) -> None:
        """Register every JARVIS tool with the authoritative registry."""

        categories = {
            "open_application": "application",
            "spotify_status": "spotify",
            "spotify_play": "spotify",
            "spotify_pause": "spotify",
            "spotify_resume": "spotify",
            "spotify_next": "spotify",
            "spotify_previous": "spotify",

            "run_command": "terminal",

            "read_file": "filesystem",
            "write_file": "filesystem",
            "edit_file": "filesystem",
            "list_directory": "filesystem",
            "search_files": "filesystem",

            "run_tests": "testing",
            "compile_project": "testing",

            "build_code_index": "code",
            "build_code_relationships": "code",
            "search_code_relationships": "code",
            "build_change_impact": "code",
            "select_tests_for_change": "code",
            "diagnose_test_failure": "code",

            "git_status": "git",
            "git_diff": "git",
            "git_diff_cached": "git",
            "git_log": "git",
            "git_branch": "git",
            "git_add": "git",
            "git_commit": "git",
            "git_push": "git",

            "health_check": "health",
            "diagnose_runtime": "health",

            "remember_memory": "memory",
            "search_memory": "memory",
            "list_memories": "memory",
            "update_memory": "memory",
            "forget_memory": "memory",
            "clear_memory": "memory",

            "index_file": "knowledge",
            "index_directory": "knowledge",
            "search_knowledge": "knowledge",
            "semantic_search": "knowledge",
            "get_document": "knowledge",
            "remove_document": "knowledge",
            "knowledge_status": "knowledge",

            "capture_screen": "vision",
            "capture_active_window": "vision",
            "analyze_image": "vision",
            "verify_screen": "vision",

            "computer_control": "computer",
            "computer_health": "computer",

            "open_browser": "browser",
            "open_url": "browser",
            "browser_search": "browser",
            "browser_action": "browser",
        }

        confirmation_tools = {
            "git_add",
            "git_commit",
            "git_push",
            "spotify_play",
            "spotify_pause",
            "spotify_resume",
            "spotify_next",
            "spotify_previous",
        }

        high_risk_tools = {
            "write_file",
            "edit_file",
            "run_command",
            "open_application",
            "computer_control",
            "open_browser",
            "open_url",
            "browser_action",
            "git_add",
            "git_commit",
            "git_push",
        }

        for tool in self.tools:
            name = tool.__name__

            description = (
                tool.__doc__ or name
            ).strip().split("\n")[0]

            metadata = ToolMetadata(
                name=name,
                description=description,
                category=categories.get(
                    name,
                    "system",
                ),
                risk_level=(
                    RiskLevel.HIGH
                    if name in high_risk_tools
                    else RiskLevel.LOW
                ),
                confirmation_required=(
                    name in confirmation_tools
                ),
            )

            self.registry.register(
                tool,
                metadata,
            )

    # ------------------------------------------------------------------
    # Confirmation API
    # ------------------------------------------------------------------

    @property
    def pending_confirmation(
        self,
    ) -> PendingConfirmation | None:
        """Return the pending confirmation, if one exists."""

        with self._confirmation_lock:
            pending = self._pending_confirmation

            if pending is not None and pending.expired:
                self._pending_confirmation = None
                return None

            return pending

    def has_pending_confirmation(self) -> bool:
        return self.pending_confirmation is not None

    def get_pending_confirmation(
        self,
    ) -> PendingConfirmation | None:
        return self.pending_confirmation

    def cancel_pending_confirmation(self) -> str:
        """Cancel the exact operation waiting for approval."""

        with self._confirmation_lock:
            pending = self._pending_confirmation

            if pending is None:
                return "There is no pending confirmation."

            self._pending_confirmation = None

        self.events.publish(
            EventType.TASK_CONFIRMATION_REQUIRED,
            task_id=pending.request_id,
            request_id=pending.request_id,
            confirmation_id=pending.confirmation_id,
            tool=pending.tool_name,
            status="cancelled",
        )

        return (
            f"Cancelled: {pending.description}"
        )

    def confirm_pending_confirmation(self) -> str:
        """Execute the exact operation previously shown to the user."""

        with self._confirmation_lock:
            pending = self._pending_confirmation

            if pending is None:
                return "There is no pending confirmation."

            if pending.expired:
                self._pending_confirmation = None
                return (
                    "That confirmation expired. "
                    "Please request the operation again."
                )

            # Consume first to prevent double execution.
            self._pending_confirmation = None

        self.logger.info(
            "Confirmation approved: id=%s tool=%s",
            pending.confirmation_id,
            pending.tool_name,
        )

        self.events.publish(
            EventType.TASK_CONFIRMATION_REQUIRED,
            task_id=pending.request_id,
            request_id=pending.request_id,
            confirmation_id=pending.confirmation_id,
            tool=pending.tool_name,
            status="approved",
        )

        try:
            permission = self.registry.permission(
                pending.tool_name,
                pending.arguments,
            )

            if permission is PermissionLevel.BLOCK:
                return (
                    "BLOCKED: Operation is no longer "
                    "permitted by the security policy."
                )

            confirmation_granted = (
                permission is PermissionLevel.CONFIRM
            )

            step = ExecutionStep(
                description=pending.description,
                tool=pending.tool_name,
                arguments=dict(pending.arguments),
            )

            report = self.execution.execute(
                [step],
                task_id=pending.request_id,
                confirmation_granted=confirmation_granted,
            )

            if not report.steps:
                return (
                    "ERROR: No execution step was performed."
                )

            result = report.steps[0].result

            if result is None:
                return (
                    f"ERROR: {pending.tool_name} "
                    "did not return an execution result."
                )

            if result.success:
                return result.message

            return (
                f"ERROR: "
                f"{result.error or result.message or 'Operation failed.'}"
            )

        except Exception as exc:
            self.logger.exception(
                "Confirmed operation failed: %s",
                pending.tool_name,
            )

            return (
                f"ERROR: Confirmed operation failed: {exc}"
            )

    # ------------------------------------------------------------------
    # Reasoning
    # ------------------------------------------------------------------

    def think(
        self,
        user_text: str,
        context: list[dict[str, str]] | None = None,
    ) -> str:
        """Reason about a request and execute required tools."""

        request_id = uuid.uuid4().hex

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
            task_id=request_id,
            request_id=request_id,
            text=user_text,
        )

        try:
            for _ in range(MAX_TOOL_ITERATIONS):
                response = self._chat_with_recovery(
                    messages
                )

                message = getattr(
                    response,
                    "message",
                    response,
                )

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
                        name, arguments = (
                            self._parse_tool_call(call)
                        )

                        if not name:
                            return (
                                "ERROR: Model produced an "
                                "invalid tool call."
                            )

                        try:
                            result = self._execute_tool(
                                name,
                                arguments,
                                request_id=request_id,
                            )

                        except ConfirmationRequired as confirmation:
                            return (
                                "CONFIRMATION REQUIRED: "
                                f"{confirmation.confirmation.description}"
                                "\n\nReply 'yes' to proceed or "
                                "'no' to cancel."
                            )

                        messages.append(
                            {
                                "role": "tool",
                                "name": name,
                                "content": result,
                            }
                        )

                    continue

                content = self._extract_content(
                    response
                )

                if content:
                    return content.strip()

                return (
                    "I completed the request but received "
                    "no textual response."
                )

            return (
                "I stopped because the tool execution limit "
                "was reached. No further actions were performed."
            )

        except Exception as exc:
            self.logger.exception(
                "Brain reasoning failed"
            )

            try:
                diagnostics = diagnose_runtime(
                    self.model_manager
                )

                record_crash(
                    str(exc),
                    gpu=diagnostics.get("gpu"),
                    ram=diagnostics.get("ram"),
                )

            except Exception:
                self.logger.exception(
                    "Runtime diagnostics failed"
                )

            self.events.publish(
                EventType.ERROR,
                task_id=request_id,
                request_id=request_id,
                message=str(exc),
            )

            return f"ERROR: {exc}"

        finally:
            metrics.finish_response(request_id)

            self.events.publish(
                EventType.THINKING_END,
                task_id=request_id,
                request_id=request_id,
            )

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    def _execute_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        request_id: str | None = None,
        confirmation_granted: bool = False,
    ) -> str:
        """Validate, authorize and execute one tool."""

        arguments = dict(arguments or {})

        if self.registry.get(name) is None:
            return json.dumps(
                {
                    "success": False,
                    "error": f"Unknown tool: {name}",
                }
            )

        validation_error = self.registry.validate(
            name,
            arguments,
        )

        if validation_error:
            return json.dumps(
                {
                    "success": False,
                    "tool": name,
                    "error": validation_error,
                    "status": "failed",
                }
            )

        permission = self.registry.permission(
            name,
            arguments,
        )

        if permission is PermissionLevel.BLOCK:
            return json.dumps(
                {
                    "success": False,
                    "tool": name,
                    "error": (
                        "BLOCKED: Operation blocked "
                        "by JARVIS security policy."
                    ),
                    "status": "blocked",
                }
            )

        if (
            permission is PermissionLevel.CONFIRM
            and not confirmation_granted
        ):
            confirmation_id = uuid.uuid4().hex[:12]

            description = self._confirmation_description(
                name,
                arguments,
            )

            pending = PendingConfirmation(
                confirmation_id=confirmation_id,
                request_id=request_id or uuid.uuid4().hex,
                tool_name=name,
                arguments=dict(arguments),
                description=description,
                created_at=time.monotonic(),
            )

            with self._confirmation_lock:
                existing = self._pending_confirmation

                if (
                    existing is not None
                    and not existing.expired
                ):
                    raise ConfirmationRequired(existing)

                self._pending_confirmation = pending

            self.events.publish(
                EventType.TASK_CONFIRMATION_REQUIRED,
                task_id=pending.request_id,
                request_id=pending.request_id,
                confirmation_id=pending.confirmation_id,
                tool=name,
                arguments=self._safe_event_arguments(
                    arguments
                ),
                description=description,
                status="pending",
            )

            self.logger.info(
                "Confirmation required: id=%s tool=%s",
                confirmation_id,
                name,
            )

            raise ConfirmationRequired(
                pending
            )

        self.events.publish(
            EventType.TOOL_START,
            task_id=request_id,
            tool=name,
            arguments=self._safe_event_arguments(
                arguments
            ),
        )

        self.logger.info(
            "Executing tool: %s",
            name,
        )

        try:
            report = self.execution.execute(
                [
                    ExecutionStep(
                        description=f"Execute {name}",
                        tool=name,
                        arguments=arguments,
                    )
                ],
                task_id=request_id,
                confirmation_granted=confirmation_granted,
            )

            if not report.steps:
                result = {
                    "success": False,
                    "error": (
                        report.stopped_reason
                        or "No execution step was performed."
                    ),
                }
            else:
                step = report.steps[0]

                if step.result is not None:
                    result = step.result.to_dict()
                else:
                    result = {
                        "success": False,
                        "error": (
                            step.error
                            or "Tool execution produced "
                            "no result."
                        ),
                    }

            success = bool(
                result.get("success", False)
            )

            self.events.publish(
                EventType.TOOL_END,
                task_id=request_id,
                tool=name,
                success=success,
            )

            return json.dumps(
                result,
                default=str,
            )

        except ConfirmationRequired:
            raise

        except Exception as exc:
            self.logger.exception(
                "Tool execution failed: %s",
                name,
            )

            self.events.publish(
                EventType.TOOL_END,
                task_id=request_id,
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

    # ------------------------------------------------------------------
    # Model handling
    # ------------------------------------------------------------------

    def _chat_with_recovery(
        self,
        messages: list[dict[str, Any]],
    ) -> Any:
        """Perform one model call and retry once after real recovery."""

        try:
            return chat(
                model=self.model,
                messages=messages,
                tools=self.tools,
                think=False,
            )

        except Exception as exc:
            self.logger.exception(
                "Model request failed"
            )

            try:
                diagnostics = diagnose_runtime(
                    self.model_manager
                )

                record_crash(
                    str(exc),
                    gpu=diagnostics.get("gpu"),
                    ram=diagnostics.get("ram"),
                )
            except Exception:
                self.logger.exception(
                    "Could not record model failure"
                )

            if (
                self.model_manager.command
                and self.model_manager.restart()
            ):
                self.events.publish(
                    EventType.TASK_RECOVERY,
                    message=(
                        "Model failure detected; "
                        "recovery attempted."
                    ),
                )

                return chat(
                    model=self.model,
                    messages=messages,
                    tools=self.tools,
                    think=False,
                )

            raise

    # ------------------------------------------------------------------
    # Compatibility permission helper
    # ------------------------------------------------------------------

    def _permission(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> PermissionLevel:
        """Compatibility helper for callers/tests."""

        if name == "run_command":
            return check_command(
                str(arguments.get("command", "")),
                self.security,
            )

        if name == "write_file":
            return check_file_write(
                str(arguments.get("path", "")),
                self.security,
            )

        if name == "edit_file":
            return check_file_edit(
                str(arguments.get("path", "")),
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

        return self.registry.permission(
            name,
            arguments,
        )

    # ------------------------------------------------------------------
    # Tool call helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_tool_call(
        call: Any,
    ) -> tuple[str, dict[str, Any]]:
        """Normalize Ollama tool-call representations."""

        if isinstance(call, dict):
            function = call.get(
                "function",
                call,
            )

            if isinstance(function, dict):
                name = function.get(
                    "name",
                    "",
                )

                arguments = function.get(
                    "arguments",
                    {},
                )

                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(
                            arguments
                        )
                    except json.JSONDecodeError:
                        arguments = {}

                return (
                    str(name),
                    dict(arguments or {}),
                )

        function = getattr(
            call,
            "function",
            None,
        )

        if function is not None:
            name = getattr(
                function,
                "name",
                "",
            )

            arguments = getattr(
                function,
                "arguments",
                {},
            )

            if isinstance(arguments, str):
                try:
                    arguments = json.loads(
                        arguments
                    )
                except json.JSONDecodeError:
                    arguments = {}

            return (
                str(name),
                dict(arguments or {}),
            )

        return "", {}

    @staticmethod
    def _extract_content(
        response: Any,
    ) -> str:
        """Extract textual content from an Ollama response."""

        if response is None:
            return ""

        if isinstance(response, str):
            return response

        if isinstance(response, dict):
            if "content" in response:
                return str(
                    response["content"] or ""
                )

            message = response.get("message")

            if isinstance(message, dict):
                return str(
                    message.get("content") or ""
                )

        content = getattr(
            response,
            "content",
            None,
        )

        if content is not None:
            return str(content)

        message = getattr(
            response,
            "message",
            None,
        )

        if message is not None:
            content = getattr(
                message,
                "content",
                None,
            )

            if content is not None:
                return str(content)

        return str(response)

    # ------------------------------------------------------------------
    # Confirmation descriptions
    # ------------------------------------------------------------------

    @staticmethod
    def _confirmation_description(
        name: str,
        arguments: dict[str, Any],
    ) -> str:
        if name == "open_application":
            application = (
                arguments.get("application")
                or arguments.get("name")
                or arguments.get("app")
                or "the application"
            )

            return (
                f"Open application: {application}"
            )

        if name == "run_command":
            command = arguments.get(
                "command",
                "",
            )

            return (
                f"Execute command: {command}"
            )

        if name in {
            "write_file",
            "edit_file",
        }:
            path = (
                arguments.get("path")
                or arguments.get("file_path")
                or arguments.get("filename")
                or "the specified file"
            )

            return (
                f"{name.replace('_', ' ').title()}: "
                f"{path}"
            )

        if name in {
            "git_add",
            "git_commit",
            "git_push",
        }:
            return (
                f"Perform Git operation: {name}"
            )

        if name in {
            "computer_control",
            "open_browser",
            "open_url",
            "browser_search",
            "browser_action",
        }:
            return (
                f"Execute computer/browser action: "
                f"{name}"
            )

        return f"Execute {name}"

    # ------------------------------------------------------------------
    # Safe event/logging arguments
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_event_arguments(
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Redact sensitive-looking values from logs/events."""

        sensitive_words = (
            "password",
            "token",
            "secret",
            "api_key",
            "apikey",
            "credential",
            "private_key",
        )

        safe: dict[str, Any] = {}

        for key, value in arguments.items():
            lowered = str(key).lower()

            if any(
                word in lowered
                for word in sensitive_words
            ):
                safe[key] = "[REDACTED]"
            else:
                safe[key] = value

        return safe

    # ------------------------------------------------------------------
    # Workflow factories
    # ------------------------------------------------------------------

    def create_coding_workflow(
        self,
        root: str,
        *,
        dry_run: bool = False,
    ):
        """Create a coding workflow using this Brain's execution boundary."""

        from app.agent.coding import CodingWorkflow

        return CodingWorkflow(
            root,
            dry_run=dry_run,
            engine=self.execution,
            registry=self.registry,
        )


__all__ = [
    "Brain",
    "PendingConfirmation",
    "ConfirmationRequired",
    "YES_RESPONSES",
    "NO_RESPONSES",
]