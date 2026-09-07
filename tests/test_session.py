"""Tests for conversation sessions."""

from app.agent.session import Session


def test_session_adds_messages():
    session = Session()

    session.add_user("Hello")
    session.add_assistant("Hi.")

    assert len(session) == 2

    messages = session.as_messages()

    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"


def test_session_trims_old_messages():
    session = Session(
        max_messages=4
    )

    for index in range(10):
        session.add_user(
            f"Message {index}"
        )

    assert len(session) == 4
    assert (
        session.messages[0].content
        == "Message 6"
    )


def test_session_clear():
    session = Session()

    session.add_user("Hello")

    session.clear()

    assert len(session) == 0
    assert session.as_messages() == []