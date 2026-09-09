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


def test_structured_failure_is_preserved():
    result = normalize_tool_result("run_tests", json.dumps({"success": False, "error": "tests failed"}))
    assert result.success is False
    assert result.error == "tests failed"
