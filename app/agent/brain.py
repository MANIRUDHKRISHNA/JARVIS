"""Core reasoning module for the JARVIS agent."""


class Brain:
    """Simple brain placeholder for orchestrating agent behavior."""

    def __init__(self, name: str = "JARVIS"):
        self.name = name

    def think(self, prompt: str) -> str:
        return f"{self.name} received: {prompt}"
