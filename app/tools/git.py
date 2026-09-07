"""Git tools for JARVIS."""

import subprocess
from pathlib import Path


def _run_git(project_path: str, args: list[str]) -> str:
    """Run a Git command inside a project."""

    path = Path(project_path)

    if not path.exists():
        return f"ERROR: Project path does not exist: {project_path}"

    if not path.is_dir():
        return f"ERROR: Project path is not a directory: {project_path}"

    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=30,
        )

        output = result.stdout.strip()
        error = result.stderr.strip()

        if result.returncode != 0:
            return (
                f"ERROR: Git command failed with exit code "
                f"{result.returncode}\n"
                f"{error or output}"
            )

        return output or "(no output)"

    except subprocess.TimeoutExpired:
        return "ERROR: Git command timed out."

    except Exception as exc:
        return f"ERROR running Git: {exc}"


def git_status(project_path: str) -> str:
    """Show the current Git working-tree status."""

    return _run_git(project_path, ["status", "--short", "--branch"])


def git_diff(project_path: str) -> str:
    """Show unstaged Git changes."""

    return _run_git(project_path, ["diff", "--"])


def git_diff_cached(project_path: str) -> str:
    """Show staged Git changes."""

    return _run_git(project_path, ["diff", "--cached", "--"])


def git_log(project_path: str, count: int = 10) -> str:
    """Show recent commits."""

    count = max(1, min(int(count), 50))

    return _run_git(
        project_path,
        ["log", f"-{count}", "--oneline", "--decorate"],
    )


def git_branch(project_path: str) -> str:
    """Show the current Git branch."""

    return _run_git(project_path, ["branch", "--show-current"])


def git_add(project_path: str, paths: list[str]) -> str:
    """Stage explicitly selected files."""

    if not paths:
        return "ERROR: No files were supplied to git_add."

    return _run_git(project_path, ["add", "--", *paths])


def git_commit(project_path: str, message: str) -> str:
    """Create a Git commit."""

    if not message or not message.strip():
        return "ERROR: Commit message cannot be empty."

    return _run_git(
        project_path,
        ["commit", "-m", message.strip()],
    )


def git_push(project_path: str) -> str:
    """Push the current branch to its configured remote."""

    return _run_git(project_path, ["push"])
