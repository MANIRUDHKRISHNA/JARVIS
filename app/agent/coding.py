"""Auditable coding workflow built on existing JARVIS repository tools."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from app.agent.capabilities import ToolMetadata, ToolRegistry
from app.agent.execution import ExecutionEngine, ExecutionLimits, ExecutionStep
from app.agent.results import ToolResult
from app.agent.security import SecurityManager
from app.tools.code_index import build_change_impact, select_tests_for_change
from app.tools.filesystem import edit_file, read_file
from app.tools.testing import run_tests
from app.tools.git import git_diff, git_status


@dataclass
class CodingContext:
    root: str
    dry_run: bool = False
    inspected: set[str] = field(default_factory=set)
    modified: list[str] = field(default_factory=list)
    tests: list[str] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)
    state: str = "IDLE"
    plan: dict = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    pre_snapshot: dict = field(default_factory=dict)

    def report(self) -> dict:
        return {"root": self.root, "dry_run": self.dry_run, "inspected": sorted(self.inspected), "modified": self.modified, "tests": self.tests, "diagnostics": self.diagnostics, "state": self.state, "plan": self.plan}


class CodingState(str, Enum):
    IDLE="IDLE"; INSPECTING="INSPECTING"; PLANNING="PLANNING"; EDITING="EDITING"; VERIFYING="VERIFYING"; TESTING="TESTING"; REVIEWING="REVIEWING"; COMPLETED="COMPLETED"; FAILED="FAILED"; BLOCKED="BLOCKED"


@dataclass
class CodingResult:
    status: CodingState
    changed: bool = False
    verified: bool = False
    tests_passed: int = 0
    tests_failed: int = 0
    failure_reason: str | None = None
    files_inspected: list[str] = field(default_factory=list)
    files_changed: list[str] = field(default_factory=list)
    tests_run: list[dict] = field(default_factory=list)
    repair_attempts: int = 0
    diff_review: dict = field(default_factory=dict)
    evidence: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {**self.__dict__, "status": self.status.value}


class CodingWorkflow:
    """Small, safe operations for coding plans; no hidden write path exists."""

    def __init__(self, root: str, security: SecurityManager | None = None, dry_run: bool = False,
                 engine: ExecutionEngine | None = None, registry: ToolRegistry | None = None, progress_callback=None):
        self.context = CodingContext(str(Path(root).resolve()), dry_run)
        self.progress_callback = progress_callback
        # A production owner supplies its existing engine.  Do not silently
        # create a parallel registry/security boundary in that case.  The
        # local construction branch remains for standalone compatibility.
        if engine is not None:
            self.engine = engine
            self.registry = registry
            self.security = security or (registry.security if registry else None)
        else:
            self.security = security or SecurityManager()
            self.registry = registry or ToolRegistry(self.security, (self.context.root,))
            if registry is None:
                self.registry.register(read_file, ToolMetadata("read_file", "Read a text file.", "filesystem"))
                self.registry.register(edit_file, ToolMetadata("edit_file", "Edit an inspected text file.", "filesystem"))
                self.registry.register(run_tests, ToolMetadata("run_tests", "Run selected tests.", "testing"))
                self.registry.register(git_status, ToolMetadata("git_status", "Show Git status.", "git"))
                self.registry.register(git_diff, ToolMetadata("git_diff", "Show Git diff.", "git"))
            self.engine = ExecutionEngine(
                self.registry.dispatch, ExecutionLimits(max_steps=1, max_tool_calls=1)
            )

    def _set_state(self, state: CodingState) -> None:
        current = CodingState(self.context.state)
        allowed = {
            CodingState.IDLE: {CodingState.INSPECTING},
            CodingState.INSPECTING: {CodingState.PLANNING, CodingState.FAILED, CodingState.BLOCKED},
            CodingState.PLANNING: {CodingState.EDITING, CodingState.FAILED, CodingState.BLOCKED},
            CodingState.EDITING: {CodingState.VERIFYING, CodingState.FAILED, CodingState.BLOCKED},
            CodingState.VERIFYING: {CodingState.TESTING, CodingState.FAILED},
            CodingState.TESTING: {CodingState.REVIEWING, CodingState.FAILED},
            CodingState.REVIEWING: {CodingState.COMPLETED, CodingState.FAILED, CodingState.BLOCKED},
        }
        if state not in {CodingState.FAILED, CodingState.BLOCKED} and state not in allowed.get(current, set()):
            raise ValueError(f"Invalid coding workflow transition: {current.value} -> {state.value}")
        self.context.state = state.value
        event = {"request_id": self.context.request_id, "phase": state.value, "status": "completed" if state in {CodingState.COMPLETED, CodingState.FAILED, CodingState.BLOCKED} else "running"}
        if self.progress_callback:
            self.progress_callback(event)

    def _snapshot(self) -> dict:
        """Read repository evidence through the registered Git tools only."""
        status = self._invoke("git_status", {"project_path": self.context.root})
        diff = self._invoke("git_diff", {"project_path": self.context.root})
        files = set()
        if not status.startswith("ERROR:"):
            for line in status.splitlines():
                if len(line) > 3 and line[:2].strip():
                    files.add(line[3:].replace("/", "\\"))
        return {"project": self.context.root, "status": status, "diff": diff, "files": sorted(files)}

    def _target_is_preexisting_change(self, path: str) -> bool:
        try:
            relative = str(Path(path).resolve().relative_to(Path(self.context.root))).replace("/", "\\")
        except ValueError:
            return True
        return relative in set(self.context.pre_snapshot.get("files", []))

    def _invoke(self, tool: str, arguments: dict, *, require_verification: bool = False) -> str:
        """Run one explicit workflow action through the authoritative boundary."""
        # Verification is owned by each tool result.  In particular, test
        # execution and edits must carry their own evidence; workflow code
        # must not promote a generic success response to verified.
        step = ExecutionStep(tool, tool, arguments)
        report = self.engine.execute([step])
        if step.result is None:
            return f"ERROR: {report.stopped_reason or 'Tool did not produce a result.'}"
        if not report.success:
            return step.result.error or step.error or step.result.message or "ERROR: Tool execution failed."
        data = step.result.data
        return data if isinstance(data, str) else json.dumps(data)

    def inspect(self, path: str) -> str:
        text = self._invoke("read_file", {"path": path})
        if not text.startswith("ERROR:"):
            self.context.inspected.add(str(Path(path).resolve()))
        return text

    def impact(self, path: str) -> str:
        return build_change_impact(self.context.root, path)

    def edit(self, path: str, old_text: str, new_text: str) -> str:
        target = Path(path).resolve()
        if str(target) not in self.context.inspected:
            return "ERROR: Refusing edit before the target has been inspected."
        if self.context.dry_run:
            return "DRY RUN: Targeted edit was planned but not applied."
        result = self._invoke("edit_file", {"path": str(target), "old_text": old_text, "new_text": new_text}, require_verification=True)
        if result.startswith("SUCCESS:"):
            self.context.modified.append(str(target))
        return result

    def test_changed(self) -> list[str]:
        if not self.context.modified:
            return []
        selected = json.loads(select_tests_for_change(self.context.root, self.context.modified[-1]))
        tests = selected.get("selected_tests", [])
        for test in tests:
            self.context.tests.append(self._invoke("run_tests", {"project_path": self.context.root, "test_path": test}))
        return self.context.tests

    def static_check(self, path: str) -> str:
        """Use the existing test tool's syntax fallback without writing code."""
        result = self._invoke("run_tests", {"project_path": self.context.root, "test_path": path})
        self.context.diagnostics.append(result)
        return result

    def plan_edit(self, task: str, path: str, old_text: str, new_text: str) -> dict:
        """Record concise operational intent; planning performs no mutation."""
        self._set_state(CodingState.PLANNING)
        self.context.plan = {"task": task, "project": self.context.root, "target_files": [str(Path(path).resolve())], "intended_modification": "replace exact inspected text", "verification": "filesystem read-back", "tests": "selected related tests", "requires_confirmation": False, "old_length": len(old_text), "new_length": len(new_text)}
        return self.context.plan.copy()

    def run_edit_request(self, task: str, path: str, old_text: str, new_text: str) -> CodingResult:
        """One bounded inspect/plan/edit/test/review request, never a free-form loop."""
        result = CodingResult(CodingState.IDLE)
        try:
            self._set_state(CodingState.INSPECTING)
            self.context.pre_snapshot = self._snapshot()
            if self._target_is_preexisting_change(path):
                result.status = CodingState.BLOCKED
                result.failure_reason = f"Target has pre-existing user changes: {path}"
                self.context.state = result.status.value
                return result
            source = self.inspect(path)
            if source.startswith(("ERROR:", "BLOCKED:")):
                result.status, result.failure_reason = CodingState.BLOCKED, source
                self.context.state = result.status.value
                return result
            result.files_inspected = sorted(self.context.inspected)
            self.plan_edit(task, path, old_text, new_text)
            result.evidence.append("inspection and structured plan completed")
            self._set_state(CodingState.EDITING)
            edit_result = self.edit(path, old_text, new_text)
            if edit_result.startswith(("ERROR:", "BLOCKED:")):
                result.status, result.failure_reason = CodingState.BLOCKED if edit_result.startswith("BLOCKED:") else CodingState.FAILED, edit_result
                self.context.state = result.status.value
                return result
            self._set_state(CodingState.VERIFYING)
            verified_source = self.inspect(path)
            if new_text not in verified_source:
                result.status, result.failure_reason = CodingState.FAILED, "File edit did not verify by read-back."
                self.context.state = result.status.value
                return result
            result.changed = result.verified = True
            result.files_changed = list(self.context.modified)
            self._set_state(CodingState.TESTING)
            for raw in self.test_changed():
                try: test = json.loads(raw)
                except json.JSONDecodeError: test = {"success": False, "verified": False, "error": raw}
                result.tests_run.append(test)
                result.tests_passed += int(test.get("passed", 0))
                result.tests_failed += int(test.get("failed", 0)) + int(test.get("errors", 0))
                if not test.get("success") or not test.get("verified"):
                    result.status, result.failure_reason = CodingState.FAILED, test.get("error") or "Selected tests did not verify."
                    self.context.state = result.status.value
                    return result
            self._set_state(CodingState.REVIEWING)
            post = self._snapshot()
            pre_files, post_files = set(self.context.pre_snapshot.get("files", [])), set(post.get("files", []))
            expected = {str(Path(item).resolve().relative_to(self.context.root)).replace("/", "\\") for item in result.files_changed}
            unexpected = sorted((post_files - pre_files) - expected)
            result.diff_review = {"pre_status": self.context.pre_snapshot.get("status"), "post_status": post.get("status"), "diff": post.get("diff"), "expected_changed_files": sorted(expected), "unexpected_changed_files": unexpected, "reviewed": True}
            if unexpected:
                result.status, result.failure_reason = CodingState.FAILED, f"Unexpected task-generated changes: {', '.join(unexpected)}"
                self.context.state = result.status.value
                return result
            self._set_state(CodingState.COMPLETED)
            result.status = CodingState.COMPLETED
            return result
        except Exception as exc:
            result.status, result.failure_reason = CodingState.FAILED, str(exc)
            self.context.state = result.status.value
            return result
