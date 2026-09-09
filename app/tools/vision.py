"""Vision tools for JARVIS."""

from __future__ import annotations

import json

from app.vision.analyzer import analyze_image as _analyze_image
from app.vision.capture import capture_active_window as _capture_active_window
from app.vision.capture import capture_screen as _capture_screen
from app.vision.verification import verify_screen as _verify_screen


def capture_screen() -> str:
    return _capture_screen()


def capture_active_window() -> str:
    return _capture_active_window()


def analyze_image(path: str, question: str | None = None) -> str:
    return json.dumps(_analyze_image(path, question), indent=2)


def verify_screen(path: str, expected: str) -> str:
    return json.dumps(_verify_screen(path, expected), indent=2)
