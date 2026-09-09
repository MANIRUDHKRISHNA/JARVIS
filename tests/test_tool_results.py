import json

from app.agent.results import normalize_tool_result


def test_legacy_success_is_not_automatically_verified():
    result = normalize_tool_result("open_application", "Successfully launched Chrome.")
    assert result.success is True
    assert result.verified is False


def test_filesystem_success_has_verification_evidence():
    result = normalize_tool_result("write_file", "SUCCESS: File written: demo.txt", {"path": "demo.txt"})
    assert result.success is True
    assert result.verified is True
    assert result.target == "demo.txt"


def test_read_result_is_verified_by_the_observed_content_not_a_generic_success_string():
    result = normalize_tool_result("read_file", "source contents", {"path": "demo.txt"})
    assert result.success is True
    assert result.verified is True

    command = normalize_tool_result("run_command", "Command completed with exit code 0.")
    assert command.success is True
    assert command.verified is False


def test_structured_failure_is_preserved():
    result = normalize_tool_result("run_tests", json.dumps({"success": False, "error": "tests failed"}))
    assert result.success is False
    assert result.error == "tests failed"
