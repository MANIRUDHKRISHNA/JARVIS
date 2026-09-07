"""Tools for Python code indexing, impact analysis, and test selection."""

from __future__ import annotations

import json
from pathlib import Path

from app.agent.indexer import (
    build_change_impact as _build_change_impact,
    build_python_index as _build_python_index,
    build_relationship_map as _build_relationship_map,
)


def build_code_index(project_path: str) -> str:
    return _build_python_index(project_path)


def build_code_relationships(project_path: str) -> str:
    return _build_relationship_map(project_path)


def search_code_relationships(project_path: str, query: str) -> str:
    result = json.loads(_build_relationship_map(project_path))
    if not result.get("success"):
        return json.dumps(result, indent=2)
    query_lower = (query or "").lower()
    matches = [item for item in result.get("relationships", []) if query_lower in json.dumps(item).lower()]
    return json.dumps({"success": True, "query": query, "match_count": len(matches), "matches": matches}, indent=2)


def build_change_impact(project_path: str, target_file: str) -> str:
    return _build_change_impact(project_path, target_file)


def select_tests_for_change(project_path: str, target_file: str) -> str:
    impact = json.loads(_build_change_impact(project_path, target_file))
    if not impact.get("success"):
        return json.dumps(impact, indent=2)
    root = Path(project_path).resolve()
    target = Path(target_file)
    if not target.is_absolute():
        target = root / target
    target = target.resolve()
    target_name = target.stem.lower()
    target_module = impact["target_module"]
    candidates = []
    test_dirs = {"tests", "test"}
    for path in root.rglob("*.py"):
        if not path.is_file() or any(part in {".git", ".venv", "__pycache__", ".pytest_cache", "node_modules"} for part in path.relative_to(root).parts):
            continue
        relative = path.relative_to(root)
        relative_string = str(relative).replace("\\", "/")
        if not (any(part in test_dirs for part in relative.parts) or path.name.startswith("test_") or path.name.endswith("_test.py")):
            continue
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        score = 0
        reasons = []
        if target_name in relative_string.lower():
            score += 100
            reasons.append("Test filename references the changed module.")
        if target_module.lower() in source.lower():
            score += 90
            reasons.append("Test source references the changed module.")
        for dependent in impact.get("dependents", []):
            module = dependent.get("from", "")
            if module and module.split(".")[-1].lower() in relative_string.lower():
                score += 50
                reasons.append(f"Test filename references dependent module {module}.")
        for dependency in impact.get("dependencies", []):
            module = dependency.get("to", "")
            if module and module.lower() in source.lower():
                score += 30
                reasons.append(f"Test references dependency {module}.")
        if score:
            candidates.append({"test": relative_string, "score": score, "reasons": reasons})
    candidates.sort(key=lambda item: (-item["score"], item["test"]))
    impact_level = impact.get("impact_level", "LOW")
    strategy = "full_suite" if impact_level == "HIGH" else "focused_then_full" if impact_level == "MEDIUM" else "focused"
    selected = [item["test"] for item in candidates[:5 if impact_level == "MEDIUM" else 3]]
    if not selected and impact_level != "LOW":
        strategy = "full_suite"
    return json.dumps({
        "success": True,
        "project_path": str(root),
        "target_file": str(target.relative_to(root)).replace("\\", "/"),
        "target_module": target_module,
        "impact_level": impact_level,
        "strategy": strategy,
        "selected_tests": selected,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "reason": "Tests were selected using static dependencies, test naming, and source references.",
        "limitations": ["Test selection is heuristic.", "Dynamic test generation and runtime dependencies are not detected.", "A focused pass does not guarantee complete coverage."],
    }, indent=2)


def diagnose_test_failure(test_result: str) -> str:
    """Extract actionable diagnostic output from a test result."""

    try:
        data = json.loads(test_result)
    except json.JSONDecodeError:
        data = {"stdout": test_result, "stderr": ""}

    if data.get("success"):
        return json.dumps({
            "success": True,
            "diagnosis": "Tests passed. No failure diagnosis required.",
        }, indent=2)

    output = f"{data.get('stdout', '')}\n{data.get('stderr', '')}".strip()
    return json.dumps({
        "success": True,
        "status": "failure",
        "exit_code": data.get("exit_code"),
        "failed": data.get("failed"),
        "errors": data.get("errors"),
        "timed_out": data.get("timed_out"),
        "diagnostic_output": output[-12000:],
        "instruction": "Use the actual diagnostic output to locate the failure before modifying code.",
    }, indent=2)
