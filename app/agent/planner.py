"""Task planning module."""


class Planner:
    """Creates a simple plan from a user request."""

    def build_plan(self, request: str):
        return {"request": request, "steps": ["analyze", "execute", "report"]}
