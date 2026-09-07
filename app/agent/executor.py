"""Execution layer for the JARVIS agent."""


class Executor:
    """Executes prepared tasks."""

    def execute(self, plan):
        return {"status": "planned", "plan": plan}
