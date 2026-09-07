"""Persistent desktop application configuration for JARVIS."""

from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
CONFIG_FILE = DATA_DIR / "config.json"

DEFAULT_CONFIG = {
    "model": "qwen3:8b",
    "window_width": 1100,
    "window_height": 750,
    "start_minimized": False,
    "minimize_to_tray": True,
    "voice_enabled": True,
    "voice_record_seconds": 5,
    "global_hotkey": "CTRL+SHIFT+J",
}


class AppConfig:
    """Load and persist user-facing JARVIS settings."""

    def __init__(self, path: Path = CONFIG_FILE):
        self.path = Path(path)
        self.values = dict(DEFAULT_CONFIG)
        self.load()

    def load(self):
        self.values = dict(DEFAULT_CONFIG)
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self.values.update(data)
        except (OSError, json.JSONDecodeError):
            self.values = dict(DEFAULT_CONFIG)

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.values, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def get(self, key: str, default=None):
        return self.values.get(key, default)

    def set(self, key: str, value):
        self.values[key] = value
