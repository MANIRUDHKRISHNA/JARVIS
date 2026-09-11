"""Bridge to the optional local cptr computer gateway."""

from __future__ import annotations

import os
from typing import Any

import requests

from app.agent.logging import logger
from app.config.computer_config import ComputerConfig


class ComputerGateway:
    def __init__(self, config: ComputerConfig | None = None):
        self.config = config or ComputerConfig.from_environment()
        self.api_key = os.getenv("JARVIS_CPTR_API_KEY", "")

    @property
    def available(self) -> bool:
        return self.config.enabled and bool(self.api_key)

    def health(self) -> dict[str, Any]:
        if not self.config.enabled:
            return {
                "available": False,
                "message": "Computer control is disabled.",
            }

        if not self.api_key:
            return {
                "available": False,
                "message": "JARVIS_CPTR_API_KEY is not configured.",
            }

        try:
            response = requests.get(
                self.config.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                },
                timeout=5,
            )

            return {
                "available": response.ok,
                "status_code": response.status_code,
                "message": (
                    "cptr gateway reachable."
                    if response.ok
                    else f"cptr gateway returned HTTP {response.status_code}."
                ),
            }

        except requests.RequestException as exc:
            return {
                "available": False,
                "message": str(exc),
            }

    def execute(self, instruction: str) -> str:
        if not self.config.enabled:
            return "ERROR: Computer control is disabled."

        if not self.api_key:
            return "ERROR: Computer gateway API key is not configured."

        if not instruction or not instruction.strip():
            return "ERROR: Empty computer instruction."

        try:
            response = requests.post(
                f"{self.config.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.config.model,
                    "messages": [
                        {
                            "role": "user",
                            "content": instruction,
                        }
                    ],
                },
                timeout=self.config.timeout,
            )

            response.raise_for_status()

            choices = response.json().get("choices", [])

            if not choices:
                return "ERROR: Computer gateway returned no response."

            return str(
                choices[0].get("message", {}).get("content", "")
            ).strip()

        except requests.RequestException as exc:
            logger.exception("Computer gateway request failed")
            return f"ERROR: Computer gateway request failed: {exc}"

        except Exception as exc:
            logger.exception("Computer control failed")
            return f"ERROR: Computer control failed: {exc}"


_gateway = ComputerGateway()


def computer_control(instruction: str) -> str:
    return _gateway.execute(instruction)


def computer_health() -> str:
    return str(_gateway.health())