"""Health-check tool for JARVIS."""

from __future__ import annotations

import json

from app.agent.health import run_health_check


def health_check() -> str:
    return json.dumps(run_health_check(), indent=2)
