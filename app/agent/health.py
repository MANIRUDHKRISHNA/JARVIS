"""JARVIS local service health checks."""

from __future__ import annotations

import requests

OLLAMA_URL = "http://127.0.0.1:11434"


def ollama_available() -> bool:
    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=2)
        return response.ok
    except requests.RequestException:
        return False


def check_services() -> dict:
    return {"ollama": ollama_available()}
