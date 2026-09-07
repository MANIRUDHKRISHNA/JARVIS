"""Static Python code indexing and change-impact analysis."""

from __future__ import annotations

import ast
import json
from pathlib import Path

IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    ".mypy_cache",
    ".ruff_cache",
}
MAX_FILE_SIZE = 2 * 1024 * 1024


def _relative_path(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def _location(node: ast.AST) -> dict:
    return {
        "line": getattr(node, "lineno", None),
        "end_line": getattr(node, "end_lineno", None),
    }


def _function_info(node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict:
    return {
        "name": node.name,
        "type": "async_function" if isinstance(node, ast.AsyncFunctionDef) else "function",
        **_location(node),
    }


def _class_info(node: ast.ClassDef) -> dict:
    return {
        "name": node.name,
        "type": "class",
        "bases": [ast.unparse(base) for base in node.bases],
        "methods": [
            _function_info(child)
            for child in node.body
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
        ],
        **_location(node),
    }


def _import_info(node: ast.Import | ast.ImportFrom) -> dict:
    if isinstance(node, ast.Import):
        return {"type": "import", "module": None, "names": [a.name for a in node.names], "line": node.lineno}
    return {
        "type": "from",
        "module": node.module or "",
        "names": [a.name for a in node.names],
        "level": node.level,
        "line": node.lineno,
    }


def index_python_file(path: Path, project_path: Path) -> dict:
    result = {"file": _relative_path(path, project_path), "classes": [], "functions": [], "imports": [], "syntax_error": None}
    try:
        if path.stat().st_size > MAX_FILE_SIZE:
            result["syntax_error"] = "File exceeds indexing size limit."
            return result
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except UnicodeDecodeError:
        result["syntax_error"] = "File is not UTF-8 text."
        return result
    except SyntaxError as exc:
        result["syntax_error"] = f"SyntaxError at line {exc.lineno}: {exc.msg}"
        return result
    except OSError as exc:
        result["syntax_error"] = f"Could not read file: {exc}"
        return result

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            result["classes"].append(_class_info(node))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result["functions"].append(_function_info(node))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            result["imports"].append(_import_info(node))
    return result


def _iter_python_files(root: Path):
    for path in root.rglob("*.py"):
        if path.is_file() and not any(part in IGNORED_DIRECTORIES for part in path.relative_to(root).parts):
            yield path


def build_python_index(project_path: str) -> str:
    root = Path(project_path).resolve()
    if not root.exists() or not root.is_dir():
        return json.dumps({"success": False, "error": f"Project does not exist or is not a directory: {root}"}, indent=2)
    files = [index_python_file(path, root) for path in _iter_python_files(root)]
    return json.dumps({
        "success": True,
        "project_path": str(root),
        "language": "Python",
        "file_count": len(files),
        "total_python_files": len(files),
        "indexed_files": sum(item["syntax_error"] is None for item in files),
        "errors": sum(item["syntax_error"] is not None for item in files),
        "files": sorted(files, key=lambda item: item["file"]),
    }, indent=2)


def _module_name(path: Path, root: Path) -> str:
    parts = list(path.relative_to(root).parts)
    if parts[-1] == "__init__.py":
        parts.pop()
    else:
        parts[-1] = Path(parts[-1]).stem
    return ".".join(parts)


def _module_map(root: Path) -> dict[str, Path]:
    return {_module_name(path, root): path for path in _iter_python_files(root) if _module_name(path, root)}


def build_relationship_map(project_path: str) -> str:
    root = Path(project_path).resolve()
    if not root.exists() or not root.is_dir():
        return json.dumps({"success": False, "error": f"Invalid project path: {root}"}, indent=2)
    modules = _module_map(root)
    relationships = []
    for path in _iter_python_files(root):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue
        source_module = _module_name(path, root)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports = [(alias.name, [alias.name]) for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                imports = [(node.module or "", [alias.name for alias in node.names])]
            else:
                continue
            for imported, names in imports:
                candidates = [imported] + [f"{imported}.{name}" for name in names]
                target_module = next((candidate for candidate in candidates if candidate in modules), None)
                if target_module:
                    relationships.append({"from": source_module, "to": target_module, "module": imported, "names": names, "line": node.lineno})
    return json.dumps({"success": True, "project_path": str(root), "relationship_count": len(relationships), "relationships": relationships}, indent=2)


def build_change_impact(project_path: str, target_file: str) -> str:
    root = Path(project_path).resolve()
    target = Path(target_file)
    if not target.is_absolute():
        target = root / target
    target = target.resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return json.dumps({"success": False, "error": "Target file is outside the project."}, indent=2)
    if not target.exists():
        return json.dumps({"success": False, "error": f"Target file does not exist: {target}"}, indent=2)
    if target.suffix.lower() != ".py":
        return json.dumps({"success": False, "error": "Change impact analysis currently supports Python files only."}, indent=2)
    index = json.loads(build_python_index(str(root)))
    graph = json.loads(build_relationship_map(str(root)))
    target_module = _module_name(target, root)
    target_info = next((item for item in index.get("files", []) if item["file"] == _relative_path(target, root)), None)
    dependencies = [item for item in graph.get("relationships", []) if item["from"] == target_module]
    dependents = [item for item in graph.get("relationships", []) if item["to"] == target_module]
    related_tests = []
    for item in index.get("files", []):
        name = Path(item["file"]).name
        if ("tests" in Path(item["file"]).parts or name.startswith("test_") or name.endswith("_test.py")) and target_module.lower() in json.dumps(item).lower():
            related_tests.append(item["file"])
    impact_level = "HIGH" if len(dependents) >= 5 else "MEDIUM" if len(dependents) >= 2 else "LOW"
    if target_info and (len(target_info.get("classes", [])) >= 2 or len(target_info.get("functions", [])) >= 5):
        impact_level = "MEDIUM"
    return json.dumps({"success": True, "project_path": str(root), "target_file": _relative_path(target, root), "target_module": target_module, "impact_level": impact_level, "target": target_info, "dependencies": dependencies, "dependents": dependents, "related_tests": related_tests, "dependency_count": len(dependencies), "dependent_count": len(dependents), "related_test_count": len(related_tests), "limitations": ["Static AST analysis only.", "Dynamic imports, plugins, reflection, and runtime-generated dependencies are not detected."]}, indent=2)
