"""Tests for the JARVIS router."""


class FakeBrain:
    def __init__(self):
        self.calls = []

    def think(self, text, context=None):
        self.calls.append(
            (text, context)
        )
        return "brain response"


class FakePlanner:
    def create_plan(self, text):
        return "1. Inspect\n2. Modify\n3. Test"


def test_router_passes_context():
    from app.agent.router import Router

    brain = FakeBrain()

    router = Router(
        brain=brain,
        planner=FakePlanner(),
    )

    context = [
        {
            "role": "user",
            "content": "Hello",
        }
    ]

    result = router.route(
        "What files are in this project?",
        context=context,
    )

    assert result == "brain response"
    assert brain.calls[0][1] == context