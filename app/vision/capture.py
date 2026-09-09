"""Privacy-preserving local screen capture helpers."""

from __future__ import annotations

import time
from pathlib import Path

SCREENSHOT_DIR = Path(__file__).resolve().parents[2] / "data" / "screenshots"


def _capture() -> str:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SCREENSHOT_DIR / f"screen_{time.strftime('%Y%m%d_%H%M%S')}.png"
    try:
        from PIL import ImageGrab
        image = ImageGrab.grab()
        image.save(path)
        return str(path)
    except ImportError:
        return "ERROR: Pillow is required for screen capture."
    except OSError as exc:
        return f"ERROR: Screen capture failed: {exc}"


def capture_screen() -> str:
    return _capture()


def capture_active_window() -> str:
    # A portable active-window capture requires an OS-specific backend;
    # fall back to the full screen rather than claiming a cropped result.
    return _capture()
