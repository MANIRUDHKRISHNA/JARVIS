from app.agent.capabilities import RiskLevel, ToolMetadata, ToolRegistry, ToolStatus
import json


def echo(text: str) -> str:
    return text


def test_registry_discovers_metadata_and_validates_input():
    registry = ToolRegistry()
    registry.register(echo, ToolMetadata("echo", "Return text", "testing", version="2", risk_level=RiskLevel.LOW))
    item = registry.inventory()[0]
    assert item["name"] == "echo" and item["available"]
    assert registry.validate("echo", {}) == "Missing required argument: text"
    assert ToolStatus.SUCCESS.value == "success"


def test_duplicate_registration_is_rejected():
    registry = ToolRegistry()
    metadata = ToolMetadata("echo", "Return text", "testing")
    registry.register(echo, metadata)
    try:
        registry.register(echo, metadata)
    except ValueError as exc:
        assert "already registered" in str(exc)
    else:
        raise AssertionError("duplicate registration was accepted")


def test_registry_dispatch_enforces_security_and_preserves_unverified_result():
    def run_command(command: str) -> str:
        return "Command completed with exit code 0."
    registry = ToolRegistry()
    registry.register(run_command, ToolMetadata("run_command", "Command", "terminal"))
    blocked = json.loads(registry.dispatch("run_command", {"command": "shutdown /s"}))
    assert not blocked["success"] and "Blocked" in blocked["error"]
    safe = json.loads(registry.dispatch("run_command", {"command": "echo ok"}))
    assert safe["success"] and not safe["verified"]


def test_registry_rejects_path_traversal_and_unapproved_roots(tmp_path):
    def read_file(path: str) -> str:
        return "content"
    registry = ToolRegistry(approved_roots=(tmp_path,))
    registry.register(read_file, ToolMetadata("read_file", "Read", "filesystem"))
    assert registry.validate("read_file", {"path": str(tmp_path / "ok.txt")}) is None
    assert "outside approved" in registry.validate("read_file", {"path": str(tmp_path / ".." / "outside.txt")})


def test_registry_treats_ui_launches_as_security_controlled_actions():
    def open_application(application: str) -> str:
        return "launched"
    registry = ToolRegistry()
    registry.register(open_application, ToolMetadata("open_application", "Launch", "system"))
    blocked = json.loads(registry.dispatch("open_application", {"application": "notepad"}))
    assert not blocked["success"] and "Confirmation required" in blocked["error"]
