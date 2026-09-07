from app.agent.model_manager import ModelManager


def test_manager_without_command_does_not_spawn():
    manager = ModelManager(command=[])
    assert manager.start() is False
    assert manager.is_alive() is False


def test_manager_restart_uses_configured_command():
    manager = ModelManager(command=["python", "-c", "import time; time.sleep(30)"])
    try:
        assert manager.start() is True
        assert manager.is_alive() is True
        assert manager.restart() is True
        assert manager.is_alive() is True
    finally:
        manager.stop()
