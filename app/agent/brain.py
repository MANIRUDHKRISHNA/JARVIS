"""JARVIS brain: local Ollama model with tool calling."""

import json
import re
from typing import Callable, Optional

from ollama import chat

from app.agent.events import EventType, get_event_bus
from app.agent.logging import logger
from app.agent.security import PermissionLevel, SecurityManager
from app.tools.applications import open_application
from app.tools.terminal import run_command
from app.tools.filesystem import (
    list_directory,
    search_files,
    read_file,
    write_file,
    edit_file,
)
from app.tools.testing import run_tests
from app.tools.health import health_check
from app.tools.computer import computer_control, computer_health
from app.tools.browser import browser_action, browser_search, open_browser, open_url
from app.tools.spotify import spotify_next, spotify_pause, spotify_play, spotify_previous, spotify_status
from app.tools.code_index import (
    build_code_index,
    search_code_relationships,
    build_code_relationships,
    build_change_impact,
    select_tests_for_change,
    diagnose_test_failure,
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


class Brain:
    """Local JARVIS reasoning and tool-execution engine."""

    def __init__(
        self,
        model: str = "qwen3:8b",
        confirm_callback: Optional[Callable[[str], bool]] = None,
    ):
        self.model = model
        self.confirm_callback = confirm_callback
        self.security = SecurityManager()
        self.events = get_event_bus()

        self.tools = [
            open_application,
            run_command,
            list_directory,
            search_files,
            read_file,
            write_file,
            edit_file,
            run_tests,
            git_status,
            git_diff,
            git_diff_cached,
            git_log,
            git_branch,
            git_add,
            git_commit,
            git_push,
            build_code_index,
            build_code_relationships,
            search_code_relationships,
            build_change_impact,
            select_tests_for_change,
            diagnose_test_failure,
            health_check,
            computer_control,
            computer_health,
            open_browser,
            open_url,
            browser_search,
            browser_action,
            spotify_status,
            spotify_play,
            spotify_pause,
            spotify_next,
            spotify_previous,
        ]

        self.max_iterations = 10

    def _system_prompt(self) -> str:
        return """
You are JARVIS, a local AI coding and computer assistant.

You have REAL tools available.

You MUST:
- Use tools when the user asks you to inspect, search, read, create,
  modify, test, debug, or execute something.
- Never pretend that a tool was executed.
- Never invent filenames, directories, file contents, command output,
  test results, or errors.
- Trust actual tool results over assumptions.
- For directory inspection use list_directory.
- For searching code use search_files.
- For reading files use read_file.
- For creating new files use write_file.
- For editing existing files use edit_file only after reading the
  actual file.
- Never invent old_text for edit_file.
- For running tests use run_tests.
- After modifying code, verify the change whenever practical.
- If a test fails, inspect the actual failure and attempt to fix it.
- Do not claim success unless the tool result confirms success.

For Git operations:
- Use git_status to inspect repository state.
- Use git_diff and git_diff_cached to inspect changes.
- Use git_log to inspect recent commits.
- Use git_branch to inspect the current branch.
- Use git_add to stage explicitly selected files.
- Use git_commit to create a commit.
- Use git_push to push changes.
- Only use git_add when the user explicitly requests staging or has
    explicitly approved a commit workflow.
- Only use git_commit after explicit user approval.
- Only use git_push after explicit user approval.
- Never create a commit or push unless the user explicitly asks.
- Never invent Git status, diffs, commit hashes, or push results.
- Never use destructive Git history operations unless explicitly requested.

For file creation:
- If the requested file does not exist, use write_file.
- Do not use edit_file with invented old_text.

For existing-file modifications:
- Read the file first.
- Make the smallest appropriate change.
- Verify the resulting file.

For tests:
- Use the dedicated run_tests tool.
- Report the actual test runner, passed, failed, errors, skipped,
  exit code, and relevant output when available.

CODE KNOWLEDGE AND IMPACT:
- Use build_code_index for Python classes, functions, methods, imports,
    and source locations.
- Use build_code_relationships or search_code_relationships for local
    static import relationships.
- Use build_change_impact before substantial changes to an existing
    Python file to identify dependencies, dependents, and related tests.
- Use select_tests_for_change to choose focused tests when appropriate.
- Test selection and impact analysis are heuristic static analysis only;
    dynamic imports, plugins, reflection, and runtime behavior may not appear.

CHANGE AND DEBUGGING WORKFLOW:
1. Read the actual file and understand the relevant code.
2. Analyze change impact and identify dependencies and dependents.
3. Select relevant tests before modifying existing Python code.
4. Make the smallest correct change and run focused tests.
5. If tests fail, use diagnose_test_failure on the actual result.
6. Locate and fix the actual cause, then rerun affected tests.
7. Run broader tests for medium or high-impact changes.
8. Never claim success without actual verification.
9. Do not modify unrelated files merely to make tests pass.

Never use permission-changing commands such as icacls or takeown
unless the user explicitly requests such an operation.

COMPUTER CONTROL:
- Use computer and browser tools only for explicit user requests.
- Never claim an application, browser, or Spotify action succeeded without
    actual tool output.
- Navigation and searching are generally safe; sending, purchasing,
    submitting, deleting, uploading, and system changes require confirmation.
- Never bypass security or disable antivirus, firewall, or Defender.
"""

    def _permission_check(self, tool_name: str, arguments: dict):
        """Check whether a potentially dangerous operation is allowed."""

        if tool_name == "run_command":
            command = arguments.get("command", "")
            return self.security.check_command(command)

        if tool_name == "write_file":
            path = arguments.get("path", "")
            return self.security.check_file_write(path)

        if tool_name == "edit_file":
            path = arguments.get("path", "")
            return self.security.check_file_edit(path)

        if tool_name == "git_commit":
            return self.security.check_git_commit()

        if tool_name == "git_add":
            return self.security.check_git_add()

        if tool_name == "git_push":
            return self.security.check_git_push()

        if tool_name == "computer_control":
            return self.security.check_computer_control(arguments.get("instruction", ""))

        return PermissionLevel.SAFE

    def _confirm(self, message: str) -> bool:
        """Request user confirmation when required."""

        if self.confirm_callback is None:
            return False

        try:
            return bool(self.confirm_callback(message))
        except Exception:
            return False

    def _execute_tool(self, tool_name: str, arguments: dict) -> str:
        """Execute one tool after security checks."""

        self.events.publish(EventType.TOOL_START, tool=tool_name, arguments=arguments)
        logger.info("Tool execution: %s %s", tool_name, arguments)
        permission = self._permission_check(tool_name, arguments)

        if permission == PermissionLevel.BLOCK:
            result = (
                "BLOCKED: Security policy does not allow this operation."
            )
            self.events.publish(EventType.ERROR, tool=tool_name, error=result)
            return result

        if permission == PermissionLevel.CONFIRM:
            description = (
                f"JARVIS wants to execute {tool_name} "
                f"with arguments:\n{json.dumps(arguments, indent=2)}"
            )

            if not self._confirm(description):
                result = "CANCELLED: User denied confirmation."
                self.events.publish(EventType.TOOL_END, tool=tool_name, result=result)
                return result

        tool_map = {
            "open_application": open_application,
            "run_command": run_command,
            "list_directory": list_directory,
            "search_files": search_files,
            "read_file": read_file,
            "write_file": write_file,
            "edit_file": edit_file,
            "run_tests": run_tests,
            "git_status": git_status,
            "git_diff": git_diff,
            "git_diff_cached": git_diff_cached,
            "git_log": git_log,
            "git_branch": git_branch,
            "git_add": git_add,
            "git_commit": git_commit,
            "git_push": git_push,
            "build_code_index": build_code_index,
            "search_code_relationships": search_code_relationships,
            "build_code_relationships": build_code_relationships,
            "build_change_impact": build_change_impact,
            "select_tests_for_change": select_tests_for_change,
            "diagnose_test_failure": diagnose_test_failure,
            "health_check": health_check,
            "computer_control": computer_control,
            "computer_health": computer_health,
            "open_browser": open_browser,
            "open_url": open_url,
            "browser_search": browser_search,
            "browser_action": browser_action,
            "spotify_status": spotify_status,
            "spotify_play": spotify_play,
            "spotify_pause": spotify_pause,
            "spotify_next": spotify_next,
            "spotify_previous": spotify_previous,
        }

        tool = tool_map.get(tool_name)

        if tool is None:
            result = f"ERROR: Unknown tool '{tool_name}'."
            self.events.publish(EventType.ERROR, tool=tool_name, error=result)
            return result

        try:
            result = tool(**arguments)

            if isinstance(result, str):
                result_text = result
            else:
                result_text = json.dumps(result, indent=2, default=str)

            self.events.publish(EventType.TOOL_END, tool=tool_name, result=result_text)
            return result_text

        except Exception as exc:
            logger.exception("Tool failed: %s", tool_name)
            result = f"ERROR executing {tool_name}: {exc}"
            self.events.publish(EventType.ERROR, tool=tool_name, error=str(exc))
            return result

    def _normalize_tool_request(self, tool_name: str, arguments: dict):
        """
        Normalize common model mistakes before execution.
        """

        if tool_name == "edit_file":
            path = arguments.get("path", "")

            if path:
                try:
                    import os

                    if not os.path.exists(path):
                        content = arguments.get("new_text", "")

                        if content:
                            return (
                                "write_file",
                                {
                                    "path": path,
                                    "content": content,
                                },
                            )
                except Exception:
                    pass

        return tool_name, arguments

    def _parse_json_tool_call(self, content: str):
        """Parse JSON tool calls emitted as ordinary text."""

        if not content:
            return None

        text = content.strip()

        if text.startswith("```"):
            text = re.sub(
                r"^```(?:json)?\s*",
                "",
                text,
                flags=re.IGNORECASE,
            )
            text = re.sub(r"\s*```$", "", text)

        try:
            data = json.loads(text)

            if isinstance(data, dict):
                tool_name = data.get("tool") or data.get("name")
                arguments = (
                    data.get("arguments")
                    or data.get("parameters")
                    or {}
                )

                if tool_name:
                    return tool_name, arguments

        except Exception:
            pass

        return None

    def _final_response(self, messages) -> str:
        """Ask the model for a final answer without tools."""

        try:
            response = chat(
                model=self.model,
                messages=messages,
                think=False,
            )

            content = response.message.content or ""

            return content.strip()

        except Exception as exc:
            return f"ERROR generating final response: {exc}"

    def think(self, user_message: str) -> str:
        """Process a user request and execute tools when needed."""

        messages = [
            {
                "role": "system",
                "content": self._system_prompt(),
            },
            {
                "role": "user",
                "content": user_message,
            },
        ]

        previous_tool_calls = set()

        for _ in range(self.max_iterations):
            try:
                response = chat(
                    model=self.model,
                    messages=messages,
                    tools=self.tools,
                    think=False,
                )
            except Exception as exc:
                return f"ERROR communicating with Ollama: {exc}"

            tool_calls = getattr(response.message, "tool_calls", None)

            if tool_calls:
                messages.append(
                    {
                        "role": "assistant",
                        "content": response.message.content or "",
                        "tool_calls": tool_calls,
                    }
                )

                for tool_call in tool_calls:
                    function = tool_call.function
                    tool_name = function.name
                    arguments = dict(function.arguments or {})

                    tool_name, arguments = self._normalize_tool_request(
                        tool_name,
                        arguments,
                    )

                    call_signature = json.dumps(
                        {
                            "tool": tool_name,
                            "arguments": arguments,
                        },
                        sort_keys=True,
                        default=str,
                    )

                    if call_signature in previous_tool_calls:
                        result = (
                            "ERROR: The same tool call was already attempted. "
                            "Do not repeat it. Use the existing result."
                        )
                    else:
                        previous_tool_calls.add(call_signature)
                        result = self._execute_tool(
                            tool_name,
                            arguments,
                        )

                    messages.append(
                        {
                            "role": "tool",
                            "name": tool_name,
                            "content": result,
                        }
                    )

                continue

            content = response.message.content or ""

            fallback = self._parse_json_tool_call(content)

            if fallback:
                tool_name, arguments = fallback

                tool_name, arguments = self._normalize_tool_request(
                    tool_name,
                    arguments,
                )

                call_signature = json.dumps(
                    {
                        "tool": tool_name,
                        "arguments": arguments,
                    },
                    sort_keys=True,
                    default=str,
                )

                if call_signature in previous_tool_calls:
                    return (
                        "ERROR: The model repeatedly requested the same "
                        "operation."
                    )

                previous_tool_calls.add(call_signature)

                result = self._execute_tool(
                    tool_name,
                    arguments,
                )

                messages.append(
                    {
                        "role": "assistant",
                        "content": content,
                    }
                )

                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"Tool result from {tool_name}:\n{result}\n\n"
                            "Continue the task using the actual result."
                        ),
                    }
                )

                continue

            return content.strip()

        return self._final_response(messages)