from app.agent.health import HealthMonitor, check_git, check_python
from app.agent.model_manager import ModelManager


def test_python_health():
    assert check_python().healthy is True


def test_git_health_structure():
    result = check_git()
    assert isinstance(result.healthy, bool)
    assert result.name == "Git"


def test_health_monitor_does_not_fake_recovery_without_command():
    result = HealthMonitor(ModelManager(command=[])).check()
    assert "no configured recovery command" in result
