"""Routes user requests to the appropriate agent actions."""


class Router:
    """Simple routing placeholder."""

    def route(self, request: str) -> str:
        if "plan" in request.lower():
            return "planner"
        return "brain"
