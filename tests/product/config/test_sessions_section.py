"""`sessions.confirm_before_dispatch`: the config contract (agent-os#169)."""

from __future__ import annotations

import pytest
import yaml
from conftest import SHIPPED_EXAMPLE_CONFIG
from pydantic import ValidationError

from agent_os.lib import load_agents_config


def config_with_sessions(tmp_path, sessions):
    data = yaml.safe_load(SHIPPED_EXAMPLE_CONFIG.read_text())
    data.pop("sessions", None)
    if sessions is not None:
        data["sessions"] = sessions
    path = tmp_path / "agents.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return path


def test_a_config_without_the_section_confirms_before_dispatch(tmp_path):
    config = load_agents_config(config_with_sessions(tmp_path, None))
    assert config.sessions.confirm_before_dispatch is True


def test_the_section_turns_the_confirmation_off(tmp_path):
    config = load_agents_config(config_with_sessions(tmp_path, {"confirm_before_dispatch": False}))
    assert config.sessions.confirm_before_dispatch is False


def test_an_unknown_key_of_the_section_is_refused(tmp_path):
    with pytest.raises((ValidationError, SystemExit, ValueError)):
        load_agents_config(config_with_sessions(tmp_path, {"confirm": True}))
