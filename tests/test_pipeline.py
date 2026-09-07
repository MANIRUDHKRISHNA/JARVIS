"""Tests for the unified agent pipeline."""

from app.agent.pipeline import AgentPipeline
from app.agent.session import Session


class FakeRouter:
    def route(self, user_text, context=None):
        assert user_text == "Hello"
        assert context is not None

        return "Hello from JARVIS."


def test_pipeline_stores_conversation():
    session = Session()

    pipeline = AgentPipeline(
        router=FakeRouter(),
        session=session,
    )

    response = pipeline.process(
        "Hello"
    )

    assert response == "Hello from JARVIS."
    assert len(session) == 2

    messages = session.as_messages()

    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Hello"

    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "Hello from JARVIS."