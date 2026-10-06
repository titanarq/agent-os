"""The `tree:` section of `config/agents.yaml`: defaults, strictness, and the example documenting it.

Expected values come from the models themselves, never from a list copied into this file, so adding
a key without documenting it in `config.example.yaml` fails here.

Pure filesystem. No backend, no network.
"""

from __future__ import annotations

import pytest
import yaml
from conftest import EXAMPLE_CONFIG
from pydantic import ValidationError

from agent_os.lib import AgentsConfig, TreeConfig, load_agents_config


def example_data() -> dict:
    return yaml.safe_load(EXAMPLE_CONFIG.read_text())


def test_the_example_config_documents_every_tree_key_and_no_other():
    assert set(example_data()["tree"]) == set(TreeConfig.model_fields)


def test_the_example_config_loads_and_its_ticket_class_is_a_worker_class():
    config = load_agents_config(EXAMPLE_CONFIG)
    assert config.tree.ticket_budget_class == "mechanical-qwen"
    assert config.classes[config.tree.ticket_budget_class].role == "worker"


def test_a_config_without_a_tree_section_loads_with_the_documented_defaults():
    data = example_data()
    del data["tree"]
    config = AgentsConfig.model_validate(data)
    assert config.tree.root == "product"
    assert config.tree.ticket_budget_class == ""
    assert config.tree.ticket_labels == []


def test_an_unknown_tree_key_fails_the_load():
    data = example_data()
    data["tree"]["rooot"] = "typo"
    with pytest.raises(ValidationError, match="rooot"):
        AgentsConfig.model_validate(data)


def test_a_ticket_class_that_is_not_defined_fails_the_load():
    data = example_data()
    data["tree"]["ticket_budget_class"] = "no-such-class"
    with pytest.raises(ValidationError, match="not a worker class"):
        AgentsConfig.model_validate(data)


def test_a_ticket_class_that_belongs_to_a_role_fails_the_load():
    data = example_data()
    data["tree"]["ticket_budget_class"] = "validator"
    with pytest.raises(ValidationError, match="not a worker class"):
        AgentsConfig.model_validate(data)
