"""Configuration for the optional local cptr computer gateway."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class ComputerConfig:
    enabled: bool = True
    base_url: str = "http://localhost:8000/v1"
    model: str = "qwen3:8b"
    timeout: int = 120

    @classmethod
    def from_environment(cls) -> "ComputerConfig":
        return cls(
            enabled=os.getenv("JARVIS_COMPUTER_ENABLED", "true").lower() == "true",
            base_url=os.getenv("JARVIS_CPTR_URL", "http://localhost:8000/v1"),
            model=os.getenv("JARVIS_CPTR_MODEL", "qwen3:8b"),
            timeout=int(os.getenv("JARVIS_CPTR_TIMEOUT", "120")),
        )
