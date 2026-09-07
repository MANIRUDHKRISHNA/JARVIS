from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from app.system.gpu import has_nvidia


class ModelManager:
    """Manage an optional local llama-server process safely."""

    def __init__(self, command: list[str] | None = None):
        self.process = None
        configured = command or os.getenv("JARVIS_MODEL_COMMAND", "")
        self.command = configured.split() if isinstance(configured, str) and configured else command

    @property
    def use_gpu(self) -> bool:
        return has_nvidia()

    def start(self):
        if not self.command:
            return False
        try:
            command = list(self.command)
            if self.use_gpu and "--gpu-layers" not in command:
                command.extend(["--gpu-layers", "999"])
            self.process = subprocess.Popen(command)
            return True
        except (OSError, ValueError):
            self.process = None
            return False

    def stop(self):
        if self.process:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
            self.process = None

    def restart(self):
        self.stop()
        time.sleep(0.1)
        return self.start()

    def is_alive(self):
        return (
            self.process is not None
            and self.process.poll() is None
        )