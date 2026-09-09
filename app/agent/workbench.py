"""Local, reviewable engineering workbench using existing JARVIS tools."""

from __future__ import annotations

import json
import platform
from dataclasses import asdict, dataclass
from pathlib import Path

from app.agent.coding import CodingWorkflow
from app.agent.capabilities import ToolRegistry
from app.agent.execution import ExecutionEngine
from app.memory.models import Memory, MemoryType
from app.memory.store import MemoryStore
from app.tools.code_index import build_code_index, build_change_impact, diagnose_test_failure, select_tests_for_change
from app.tools.git import git_branch, git_status
from app.agent.execution import ExecutionStep


@dataclass
class ProjectSnapshot:
    root: str
    branch: str
    git_status: str
    changed_files: list[str]
    indexed_files: int
    tests: list[str]
    python_version: str
    tools: list[dict]

    def as_dict(self): return asdict(self)


class EngineeringWorkbench:
    def __init__(self, root: str, engine: ExecutionEngine, registry: ToolRegistry | None = None, memory: MemoryStore | None = None):
        """Use an explicitly owned execution engine; never create one here."""
        self.root = Path(root).resolve()
        self.registry, self.memory = registry, memory or MemoryStore()
        self.engine = engine
        self.workflow = CodingWorkflow(str(self.root), engine=engine, registry=registry)

    def _execute(self, tool: str, arguments: dict) -> dict:
        step = ExecutionStep(tool, tool, arguments, verify=lambda result: result.success)
        report = self.engine.execute([step])
        if step.result is None:
            return {"success": False, "verified": False, "error": report.stopped_reason or "Tool did not return a result."}
        data = step.result.data
        payload = data if isinstance(data, dict) else {"success": step.result.success, "verified": step.result.verified, "output": data}
        if not report.success:
            payload = {**payload, "success": False, "verified": False, "error": step.error or step.result.error}
        return payload

    def snapshot(self) -> ProjectSnapshot:
        index = json.loads(build_code_index(str(self.root)))
        status = git_status(str(self.root))
        changed = [line[3:] for line in status.splitlines() if len(line) > 3 and line[:2].strip()]
        return ProjectSnapshot(str(self.root), git_branch(str(self.root)), status, changed, len(index.get("files", [])), [str(p.relative_to(self.root)).replace("\\", "/") for p in self.root.rglob("test_*.py")], platform.python_version(), self.registry.inventory() if self.registry else [])

    def diagnose(self) -> dict:
        checks = []
        syntax = self._execute("compile_project", {"project_path": str(self.root)})
        checks.append({"name": "compileall", "healthy": bool(syntax.get("success")) and bool(syntax.get("verified")), "output": (str(syntax.get("stdout", "")) + str(syntax.get("stderr", "")))[-4000:]})
        checks.append({"name": "git", "healthy": not git_status(str(self.root)).startswith("ERROR:"), "output": git_status(str(self.root))})
        if self.registry:
            checks.extend({"name": item["name"], "healthy": item["available"], "output": item["availability_reason"]} for item in self.registry.inventory())
        return {"success": all(item["healthy"] for item in checks if item["name"] in {"compileall", "git"}), "checks": checks}

    def targeted_tests(self, changed_file: str) -> dict:
        impact = json.loads(build_change_impact(str(self.root), changed_file))
        selection = json.loads(select_tests_for_change(str(self.root), changed_file))
        results = [self._execute("run_tests", {"project_path": str(self.root), "test_path": test}) for test in selection.get("selected_tests", [])]
        return {"success": all(result.get("success") for result in results), "impact": impact, "selection": selection, "results": results}

    def diagnose_failure(self, test_result: str) -> dict:
        return json.loads(diagnose_test_failure(test_result))

    def remember_decision(self, text: str) -> int | None:
        return self.memory.add(Memory(None, text, MemoryType.DECISION, importance=0.8, confidence=1.0, source="project", project=str(self.root)))
