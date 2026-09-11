import json

from app.agent.capabilities import ToolMetadata, ToolRegistry
from app.tools import browser


def test_browser_search_rejects_empty_query():
    assert browser.browser_search("").startswith("ERROR:")


def test_browser_search_rejects_invalid_result_limit():
    assert browser.browser_search("JARVIS", max_results=0).startswith("ERROR:")
    assert browser.browser_search("JARVIS", max_results=11).startswith("ERROR:")


def test_browser_search_uses_google_research_instruction(monkeypatch):
    captured = {}

    def fake_computer_control(instruction: str) -> str:
        captured["instruction"] = instruction
        return "RESULT 1\nTITLE: The Mentalist\nURL: https://example.com\nSNIPPET: test"

    monkeypatch.setattr(browser, "computer_control", fake_computer_control)

    result = browser.browser_search("who played Red John", max_results=3)

    assert "RESULT 1" in result
    assert "who played Red John" in captured["instruction"]
    assert "Use Google Search" in captured["instruction"]
    assert "up to 3" in captured["instruction"]
    assert "Do not invent URLs" in captured["instruction"]


def test_browser_search_is_read_only_and_does_not_require_confirmation():
    def browser_search(query: str) -> str:
        return "RESULT 1"

    registry = ToolRegistry()
    registry.register(
        browser_search,
        ToolMetadata("browser_search", "Google research", "browser"),
    )

    result = json.loads(
        registry.dispatch("browser_search", {"query": "The Mentalist"})
    )

    assert result["success"]
