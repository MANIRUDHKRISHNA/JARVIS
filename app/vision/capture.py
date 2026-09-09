"""Privacy-preserving local screen capture helpers."""

from __future__ import annotations

import tempfile
from pathlib import Path

def _capture() -> str:
    try:
        from PIL import ImageGrab
        # Screenshots can contain credentials. Keep them temporary rather than
        # silently building a permanent private screenshot archive.
        handle = tempfile.NamedTemporaryFile(prefix="jarvis-screen-", suffix=".png", delete=False)
        path = Path(handle.name)
        handle.close()
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
