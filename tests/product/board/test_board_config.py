import yaml
from conftest import SHIPPED_EXAMPLE_CONFIG

from agent_os.lib import BoardConfig, load_agents_config


def test_the_example_config_documents_every_board_key_and_no_other():
    assert set(yaml.safe_load(SHIPPED_EXAMPLE_CONFIG.read_text())["board"]) == set(
        BoardConfig.model_fields
    )


def test_the_documented_values_are_the_defaults():
    documented = yaml.safe_load(SHIPPED_EXAMPLE_CONFIG.read_text())["board"]
    assert BoardConfig(**documented) == BoardConfig()
    assert load_agents_config(SHIPPED_EXAMPLE_CONFIG).board == BoardConfig()
