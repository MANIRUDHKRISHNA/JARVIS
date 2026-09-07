from pathlib import Path

from app.config.app_config import AppConfig


def test_config_defaults(tmp_path: Path):
    config = AppConfig(tmp_path / "config.json")

    assert config.get("model") == "qwen3:8b"
    assert config.get("minimize_to_tray") is True


def test_config_save_and_load(tmp_path: Path):
    path = tmp_path / "config.json"
    config = AppConfig(path)
    config.set("model", "test-model")
    config.save()

    loaded = AppConfig(path)

    assert loaded.get("model") == "test-model"
