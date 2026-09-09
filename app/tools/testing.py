"""Testing and verification tools for JARVIS."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

MAX_TIMEOUT = 300


def _validate_project(project_path: str):
    root = Path(project_path).resolve()
    if not root.exists():
        return None, f"Project does not exist: {root}"
    if not root.is_dir():
        return None, f"Project path is not a directory: {root}"
    return root, None


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _run(command: list[str], cwd: Path, timeout: int) -> dict:
    start = time.perf_counter()
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=min(max(int(timeout), 1), MAX_TIMEOUT),
            encoding="utf-8",
            errors="replace",
        )
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "duration_seconds": round(time.perf_counter() - start, 3),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        return {
            "exit_code": -1,
            "stdout": stdout,
            "stderr": str(stderr) + "\nExecution timed out.",
            "duration_seconds": round(time.perf_counter() - start, 3),
            "timed_out": True,
        }


def _pytest_counts(stdout: str, stderr: str) -> dict:
    text = f"{stdout}\n{stderr}"
    counts = {}
    for pattern, key in [
        (r"(\d+)\s+passed", "passed"),
        (r"(\d+)\s+failed", "failed"),
        (r"(\d+)\s+errors?", "errors"),
        (r"(\d+)\s+skipped", "skipped"),
    ]:
        match = re.search(pattern, text)
        counts[key] = int(match.group(1)) if match else 0
    return counts


def run_tests(project_path: str, test_path: str | None = None, timeout: int = 120) -> str:
    """Run pytest or perform syntax verification."""
    root, error = _validate_project(project_path)
    if error:
        return json.dumps({"success": False, "error": error}, indent=2)

    target = None
    if test_path:
        target = Path(test_path)
        if not target.is_absolute():
            target = root / target
        target = target.resolve()
        if not _inside(target, root):
            return json.dumps({"success": False, "error": "Test path is outside the project."}, indent=2)
        if not target.exists():
            return json.dumps({"success": False, "error": f"Test path does not exist: {target}"}, indent=2)

    pytest_check = _run([sys.executable, "-m", "pytest", "--version"], root, 30)
    if pytest_check["exit_code"] == 0:
        command = [sys.executable, "-m", "pytest"]
        if target:
            command.append(str(target))
        result = _run(command, root, timeout)
        counts = _pytest_counts(result["stdout"], result["stderr"])
        return json.dumps({
            "success": result["exit_code"] == 0 and not result["timed_out"],
            "verified": result["exit_code"] == 0 and not result["timed_out"],
            "test_runner": "pytest",
            "target": str(target.relative_to(root)).replace("\\", "/") if target else None,
            **result,
            **counts,
        }, indent=2)

    if target and target.suffix.lower() == ".py":
        result = _run([sys.executable, "-m", "py_compile", str(target)], root, timeout)
        return json.dumps({
            "success": result["exit_code"] == 0 and not result["timed_out"],
            "verified": result["exit_code"] == 0 and not result["timed_out"],
            "test_runner": "py_compile",
            "target": str(target),
            "passed": 0,
            "failed": 0,
            "errors": 0 if result["exit_code"] == 0 else 1,
            "skipped": 0,
            "note": "Pytest unavailable. Only syntax verification was performed.",
            **result,
        }, indent=2)

    return json.dumps({"success": False, "error": "Pytest is unavailable.", "test_runner": None}, indent=2)


def compile_project(project_path: str, timeout: int = 120) -> str:
    """Compile the project's app and tests directories with verified output."""
    root, error = _validate_project(project_path)
    if error:
        return json.dumps({"success": False, "verified": False, "error": error})
    result = _run([sys.executable, "-m", "compileall", "-q", "app", "tests"], root, timeout)
    success = result["exit_code"] == 0 and not result["timed_out"]
    return json.dumps({
        "success": success,
        "verified": success,
        "check": "compileall",
        **result,
    }, indent=2)
