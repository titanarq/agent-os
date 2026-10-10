"""`puntal.action_models`: one action of a host may run on a model of its own, the others on the
puntal class's. Nothing here spends a turn: every launch goes to the fake `claude` (see
`test_puntal_task.py`)."""

from __future__ import annotations

import json

import pytest

from agent_os.lib import PuntalConfig, load_role_class

pytestmark = pytest.mark.usefixtures("no_real_backend")

from puntal_support import (
    drive,
    puntal_environment,  # noqa: F401  (the `environment` fixture)
    telemetry_of,
    write_config,
)


def launched_model(tmp_path) -> str:
    argv = json.loads((tmp_path / "argv.log").read_text().splitlines()[0])["argv"]
    return argv[argv.index("--model") + 1]


def test_an_action_named_in_action_models_runs_on_its_own_model_and_the_telemetry_says_so(
    environment, tmp_path
):
    write_config(tmp_path, puntal_section={"action_models": {"create_ticket": "action-model"}})
    result = drive(environment, payload={})
    assert result.returncode == 0, result.stderr
    assert launched_model(tmp_path) == "action-model"
    record = telemetry_of(tmp_path)[0]
    assert record["model"] == "action-model"
    assert record["versions"]["model"] == "action-model"


def test_an_action_that_action_models_does_not_name_keeps_the_class_s_model(environment, tmp_path):
    write_config(tmp_path, puntal_section={"action_models": {"another_action": "action-model"}})
    class_model = load_role_class("puntal", path=tmp_path / "agents.yaml")[1].model
    assert drive(environment, payload={}).returncode == 0
    assert launched_model(tmp_path) == class_model != "action-model"


def test_the_model_flag_outranks_the_action_s_model(environment, tmp_path):
    write_config(tmp_path, puntal_section={"action_models": {"create_ticket": "action-model"}})
    assert drive(environment, "--model", "flag-model", payload={}).returncode == 0
    assert launched_model(tmp_path) == "flag-model"


def test_an_action_that_names_no_model_is_refused_at_load():
    with pytest.raises(ValueError, match="create_ticket"):
        PuntalConfig(action_models={"create_ticket": " "})
