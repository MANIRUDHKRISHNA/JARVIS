"""JARVIS health, runtime diagnostics, and recovery helpers."""

from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from app.agent.model_manager import ModelManager
from app.system.gpu import diagnostics as gpu_diagnostics

CRASH_DIR = Path(__file__).resolve().parents[2] / "logs" / "crashes"


@dataclass
class HealthResult:
    name: str
    healthy: bool
    message: str
    details: dict[str, Any]


class HealthMonitor:
    def __init__(self, manager: ModelManager | None = None):
        self.manager = manager or ModelManager()

    def check(self) -> str:
        if self.manager.is_alive():
            return "Healthy."
        if self.manager.command and self.manager.restart():
            return "Model restarted."
        return "Model is not running; no configured recovery command is available."


def record_crash(error: str, gpu: bool | None = None, ram: int | None = None) -> Path:
    CRASH_DIR.mkdir(parents=True, exist_ok=True)
    path = CRASH_DIR / f"crash-{time.strftime('%Y%m%d-%H%M%S')}-{time.time_ns()}.json"
    path.write_text(json.dumps({"time": time.strftime('%Y-%m-%dT%H:%M:%S%z'), "error": str(error), "gpu": gpu, "ram": ram}, indent=2), encoding="utf-8")
    return path


def check_ollama() -> HealthResult:
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=3)
        if response.ok:
            return HealthResult("Ollama", True, "Ollama is running.", {"models": len(response.json().get("models", []))})
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
        inputs = [device for device in sd.query_devices() if device.get("max_input_channels", 0) > 0]
        return HealthResult("Microphone", bool(inputs), "Microphone input is available." if inputs else "No microphone input device found.", {"input_devices": len(inputs)})
    except Exception as exc:
        return HealthResult("Microphone", False, f"Microphone check failed: {exc}", {})


def check_disk() -> HealthResult:
    try:
        usage = shutil.disk_usage(Path.cwd())
        return HealthResult("Disk", True, "Disk status available.", {"free_bytes": usage.free, "total_bytes": usage.total})
    except OSError as exc:
        return HealthResult("Disk", False, f"Disk check failed: {exc}", {})


def check_computer_gateway() -> HealthResult:
    try:
        from app.tools.computer import ComputerGateway
        result = ComputerGateway().health()
        return HealthResult("Computer", bool(result.get("available")), str(result.get("message", "Unavailable.")), {})
    except Exception as exc:
        return HealthResult("Computer", False, f"Computer gateway check failed: {exc}", {})


def check_stt() -> HealthResult:
    try:
        import faster_whisper  # noqa: F401
        return HealthResult("STT", True, "faster-whisper is installed; model loads on first use.", {})
    except ImportError:
        return HealthResult("STT", False, "faster-whisper is not installed.", {})


def check_tts() -> HealthResult:
    try:
        import pyttsx3  # noqa: F401
        return HealthResult("TTS", True, "pyttsx3 is installed; voice engine initializes on first use.", {})
    except ImportError:
        return HealthResult("TTS", False, "pyttsx3 is not installed.", {})


def run_health_check() -> dict[str, Any]:
    results = [check_python(), check_ollama(), check_git(), check_microphone(), check_disk(), check_computer_gateway(), check_stt(), check_tts()]
    return {"healthy": all(item.healthy for item in results), "checks": {item.name: {"healthy": item.healthy, "message": item.message, "details": item.details} for item in results}}


def ollama_available() -> bool:
    return check_ollama().healthy


def diagnose_runtime(manager: ModelManager | None = None) -> dict[str, Any]:
    manager = manager or ModelManager()
    result = {**gpu_diagnostics(), "model_alive": manager.is_alive(), "cpu": None, "ram": None}
    try:
        import psutil
        result["cpu"] = psutil.cpu_percent(interval=0.1)
        result["ram"] = psutil.virtual_memory().percent
    except ImportError:
        result["metrics_note"] = "Install psutil for CPU and RAM percentages."
    return result
