"""Structured local perception, preferring operating-system state to vision."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class PerceptionSnapshot:
    timestamp: float
    active_window: str | None = None
    process: str | None = None
    browser: dict[str, Any] | None = None
    url: str | None = None
    page_title: str | None = None
    visible_elements: list[dict[str, Any]] | None = None
    screen: dict[str, int] | None = None
    screenshot_reference: str | None = None
    confidence: str = "low"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def capture_snapshot(capture=None, structured_state=None) -> PerceptionSnapshot:
    snapshot = PerceptionSnapshot(timestamp=time.time())
    try:
        import ctypes
        import win32gui
        hwnd = win32gui.GetForegroundWindow()
        snapshot.active_window = win32gui.GetWindowText(hwnd) or None
        snapshot.screen = {"width": ctypes.windll.user32.GetSystemMetrics(0), "height": ctypes.windll.user32.GetSystemMetrics(1)}
        snapshot.confidence = "high" if snapshot.active_window else "medium"
    except Exception:
        pass
    if structured_state:
        try:
            state = structured_state() or {}
            for name in ("active_window", "process", "browser", "url", "page_title", "visible_elements", "screen"):
                if name in state and state[name] is not None:
                    setattr(snapshot, name, state[name])
            snapshot.confidence = "high" if any((snapshot.active_window, snapshot.url, snapshot.visible_elements)) else snapshot.confidence
        except Exception:
            pass
    if snapshot.active_window is None and not snapshot.url and capture:
        snapshot.screenshot_reference = capture()
        snapshot.confidence = "medium" if snapshot.screenshot_reference and not str(snapshot.screenshot_reference).startswith("ERROR:") else "low"
    return snapshot


def state_changed(before: PerceptionSnapshot, after: PerceptionSnapshot) -> bool:
    return (before.active_window, before.process, before.url, before.page_title, before.visible_elements, before.screenshot_reference) != (after.active_window, after.process, after.url, after.page_title, after.visible_elements, after.screenshot_reference)


def find_target(snapshot: PerceptionSnapshot, target: str) -> dict[str, Any] | None:
    """Resolve a UI target from structured DOM/accessibility observations only."""
    needle = target.strip().lower()
    for element in snapshot.visible_elements or []:
        text = " ".join(str(element.get(key, "")) for key in ("name", "label", "text", "id")).lower()
        if needle and needle in text:
            found = dict(element)
            found["confidence"] = element.get("confidence", "high")
            return found
    return None


def verify_action(before: PerceptionSnapshot, after: PerceptionSnapshot, target: str | None = None) -> dict[str, Any]:
    changed = state_changed(before, after)
    target_present = bool(find_target(after, target)) if target else True
    return {"success": changed and target_present, "verified": changed and target_present, "changed": changed, "target": target, "before": before.as_dict(), "after": after.as_dict()}
