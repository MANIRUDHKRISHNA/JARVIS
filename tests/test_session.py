from app.agent.session import Session


def test_session_stores_messages():
    session = Session()
    session.add_user("Hello")
    session.add_assistant("Hello, human.")

    messages = session.as_messages()

    assert len(messages) == 2
    assert messages[0] == {"role": "user", "content": "Hello"}
    assert messages[1]["role"] == "assistant"


def test_session_clear():
    session = Session()
    session.add_user("Test")
    session.clear()
    assert session.as_messages() == []


def test_session_trim():
    session = Session(max_messages=2)
    session.add_user("one")
    session.add_user("two")
    session.add_user("three")

    messages = session.as_messages()

    assert len(messages) == 2
    assert messages[0]["content"] == "two"
    assert messages[1]["content"] == "three"