import subprocess

from app.agent.brain import Brain
from app.agent.security import PermissionLevel
from app.tools.git import (
    git_add,
    git_branch,
    git_diff,
    git_diff_cached,
    git_log,
    git_status,
)


def initialize_repository(path):
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "tests@example.com"],
        cwd=path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "JARVIS Tests"],
        cwd=path,
        check=True,
    )


def git_command(path, *args):
    return subprocess.run(
        ["git", *args],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )


def test_git_inspection_tools(tmp_path):
    initialize_repository(tmp_path)
    source_file = tmp_path / "example.py"
    source_file.write_text("value = 1\n", encoding="utf-8")

    status = git_status(str(tmp_path))
    assert "## No commits yet on main" in status
    assert "?? example.py" in status

    git_command(tmp_path, "add", "example.py")
    git_command(tmp_path, "commit", "-m", "Initial test commit")
    source_file.write_text("value = 2\n", encoding="utf-8")

    assert git_branch(str(tmp_path)) == "main"
    assert "value = 2" in git_diff(str(tmp_path))
    assert git_diff_cached(str(tmp_path)) == "(no output)"
    assert "Initial test commit" in git_log(str(tmp_path), count=5)


def test_git_tools_validate_project_path(tmp_path):
    missing_path = tmp_path / "missing"

    result = git_status(str(missing_path))

    assert result.startswith("ERROR: Project path does not exist")


def test_git_add_requires_paths(tmp_path):
    initialize_repository(tmp_path)

    assert git_add(str(tmp_path), []) == (
        "ERROR: No files were supplied to git_add."
    )


def test_git_add_stages_selected_file(tmp_path):
    initialize_repository(tmp_path)
    source_file = tmp_path / "example.py"
    source_file.write_text("value = 1\n", encoding="utf-8")

    result = git_add(str(tmp_path), ["example.py"])

    assert result == "(no output)"
    status = git_status(str(tmp_path))
    assert "A  example.py" in status


def test_git_commit_and_push_require_confirmation():
    brain = Brain(
        confirm_callback=lambda message: False,
    )

    assert brain.security.check_git_commit() == PermissionLevel.CONFIRM
    assert brain.security.check_git_add() == PermissionLevel.CONFIRM
    assert brain.security.check_git_push() == PermissionLevel.CONFIRM
    assert (
        brain._execute_tool(
            "git_add",
            {"project_path": ".", "paths": ["app/agent/brain.py"]},
        )
        == "CANCELLED: User denied confirmation."
    )
    assert (
        brain._execute_tool(
            "git_commit",
            {"project_path": ".", "message": "test"},
        )
        == "CANCELLED: User denied confirmation."
    )
    assert (
        brain._execute_tool(
            "git_push",
            {"project_path": "."},
        )
        == "CANCELLED: User denied confirmation."
    )