from app.agent.health import check_git, check_python


def test_python_health():
    assert check_python().healthy is True


def test_git_health_structure():
    result = check_git()
    assert isinstance(result.healthy, bool)
    assert result.name == "Git"
