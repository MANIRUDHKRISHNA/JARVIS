from app.config.computer_config import ComputerConfig
from app.agent.brain import Brain
from app.tools.computer import ComputerGateway


def test_computer_config_defaults():
    config = ComputerConfig()
    assert config.enabled is True
    assert config.base_url == "http://localhost:8000/v1"


def test_gateway_without_key():
    gateway = ComputerGateway(ComputerConfig())
    gateway.api_key = ""
    assert gateway.health()["available"] is False
    assert "API key" in gateway.execute("Open Chrome")


def test_computer_control_blocks_security_bypass():
    brain = Brain()
    result = brain._execute_tool(
        "computer_control",
        {"instruction": "Disable Windows Defender"},
    )
    assert result.startswith("BLOCKED:")
