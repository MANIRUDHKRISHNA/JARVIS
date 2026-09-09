"""Auditable coding workflow built on existing JARVIS repository tools."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from app.agent.capabilities import ToolMetadata, ToolRegistry
from app.agent.execution import ExecutionEngine, ExecutionLimits, ExecutionStep
from app.agent.security import SecurityManager
from app.tools.code_index import build_change_impact, select_tests_for_change
from app.tools.filesystem import edit_file, read_file
from app.tools.testing import run_tests


@dataclass
class CodingContext:
    root: str
    dry_run: bool = False
    inspected: set[str] = field(default_factory=set)
    modified: list[str] = field(default_factory=list)
    tests: list[str] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)

    def report(self) -> dict:
        return {"root": self.root, "dry_run": self.dry_run, "inspected": sorted(self.inspected), "modified": self.modified, "tests": self.tests, "diagnostics": self.diagnostics}


class CodingWorkflow:
    """Small, safe operations for coding plans; no hidden write path exists."""

    def __init__(self, root: str, security: SecurityManager | None = None, dry_run: bool = False,
                 engine: ExecutionEngine | None = None, registry: ToolRegistry | None = None):
        self.context = CodingContext(str(Path(root).resolve()), dry_run)
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
            self.engine = ExecutionEngine(
                self.registry.dispatch, ExecutionLimits(max_steps=1, max_tool_calls=1)
            )

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
