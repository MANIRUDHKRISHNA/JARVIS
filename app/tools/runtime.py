"""Runtime diagnostics tools for JARVIS."""

from __future__ import annotations

import json

from app.agent.health import diagnose_runtime as _diagnose_runtime


def diagnose_runtime() -> str:
    """Return GPU, model, CPU, and memory diagnostics."""

    return json.dumps(_diagnose_runtime(), indent=2)


