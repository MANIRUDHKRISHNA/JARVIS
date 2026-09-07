"""Runtime performance metrics for JARVIS."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from threading import Lock

from app.system.gpu import diagnostics as gpu_diagnostics

METRICS_FILE = Path(__file__).resolve().parents[2] / "data" / "metrics.json"


class Metrics:
    """Collect lightweight runtime metrics without requiring psutil."""

    def __init__(self, path: Path = METRICS_FILE):
        self.path = Path(path)
        self._lock = Lock()
        self._started: dict[str, float] = {}

    def start_response(self, request_id: str) -> None:
        self._started[request_id] = time.perf_counter()

    def finish_response(self, request_id: str, tokens: int | None = None) -> dict:
        started = self._started.pop(request_id, time.perf_counter())
        result = {
            "response_time": round(time.perf_counter() - started, 3),
            "tokens_per_second": None,
            "cpu_usage": None,
            "gpu_usage": None,
            "memory_usage": None,
        }
        try:
            import psutil

            result["cpu_usage"] = psutil.cpu_percent(interval=0.1)
            result["memory_usage"] = psutil.virtual_memory().percent
        except ImportError:
            pass
        if tokens is not None and result["response_time"] > 0:
            result["tokens_per_second"] = round(tokens / result["response_time"], 2)
        result.update(gpu_diagnostics())
        self.record(result)
        return result

    def record(self, values: dict) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            history = []
            if self.path.exists():
                try:
                    history = json.loads(self.path.read_text(encoding="utf-8"))
                    if not isinstance(history, list):
                        history = []
                except (OSError, json.JSONDecodeError):
                    history = []
            history.append({"time": time.time(), **values})
            self.path.write_text(json.dumps(history[-500:], indent=2), encoding="utf-8")


metrics = Metrics()
