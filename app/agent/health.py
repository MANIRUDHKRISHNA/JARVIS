"""JARVIS health and dependency checks."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from typing import Any

import requests


@dataclass
class HealthResult:
    name: str
    healthy: bool
    message: str
    details: dict[str, Any]


def check_ollama() -> HealthResult:
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=3)
        if response.ok:
            models = response.json().get("models", [])
            return HealthResult("Ollama", True, "Ollama is running.", {"models": len(models)})
        return HealthResult("Ollama", False, f"Ollama returned HTTP {response.status_code}.", {})
    except Exception as exc:
        return HealthResult("Ollama", False, f"Ollama unavailable: {exc}", {})


def check_python() -> HealthResult:
    return HealthResult("Python", True, "Python runtime is available.", {})


def check_git() -> HealthResult:
    path = shutil.which("git")
    return HealthResult("Git", path is not None, "Git is available." if path else "Git executable was not found.", {"path": path})


def check_microphone() -> HealthResult:
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        inputs = [device for device in devices if device.get("max_input_channels", 0) > 0]
        return HealthResult("Microphone", bool(inputs), "Microphone input is available." if inputs else "No microphone input device found.", {"input_devices": len(inputs)})
    except Exception as exc:
        return HealthResult("Microphone", False, f"Microphone check failed: {exc}", {})


def run_health_check() -> dict[str, Any]:
    results = [check_python(), check_ollama(), check_git(), check_microphone()]
    from app.tools.computer import computer_health

    computer = computer_health()
    return {
        "healthy": all(result.healthy for result in results) and "'available': True" in computer,
        "checks": {
            **{result.name: {"healthy": result.healthy, "message": result.message, "details": result.details} for result in results},
            "Computer Control": {"healthy": "'available': True" in computer, "message": computer, "details": {}},
        },
    }


def ollama_available() -> bool:
    return check_ollama().healthy
