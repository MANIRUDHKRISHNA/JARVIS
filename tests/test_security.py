from app.agent.security import (
    PermissionLevel,
    SecurityManager,
    check_command,
    check_file_edit,
    check_file_write,
)


def test_safe_command():
    security = SecurityManager()

    result = security.check_command(
        "python --version"
    )

    assert result == PermissionLevel.SAFE


def test_dangerous_command_is_blocked():
    security = SecurityManager()

    result = security.check_command(
        "format C:"
    )

    assert result == PermissionLevel.BLOCK


def test_shutdown_is_blocked():
    security = SecurityManager()

    result = security.check_command(
        "shutdown /s /t 0"
    )

    assert result == PermissionLevel.BLOCK


def test_pip_install_requires_confirmation():
    security = SecurityManager()

    result = security.check_command(
        "pip install requests"
    )

    assert result == PermissionLevel.CONFIRM


def test_git_push_requires_confirmation():
    security = SecurityManager()

    result = security.check_command(
        "git push"
    )

    assert result == PermissionLevel.CONFIRM


def test_normal_project_file_is_safe():
    security = SecurityManager()

    result = security.check_file_write(
        r"D:\JARVIS\app\example.py"
    )

    assert result == PermissionLevel.SAFE


def test_env_file_requires_confirmation():
    security = SecurityManager()

    result = security.check_file_write(
        r"D:\JARVIS\.env"
    )

    assert result == PermissionLevel.CONFIRM


def test_sensitive_file_edit_requires_confirmation():
    security = SecurityManager()

    result = security.check_file_edit(
        r"D:\JARVIS\secrets\config.json"
    )

    assert result == PermissionLevel.CONFIRM


def test_standalone_helpers_work():
    assert check_command("python --version") == PermissionLevel.SAFE

    assert (
        check_file_write(r"D:\JARVIS\app\main.py")
        == PermissionLevel.SAFE
    )

    assert (
        check_file_edit(r"D:\JARVIS\.env")
        == PermissionLevel.CONFIRM
    )