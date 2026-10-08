"""The fast path plans operations over the app's data, so its contract carries the app's data API.

`puntal.persistence_api_file` used to be rendered into the SLOW path's contract only. The fast turn
has no tool and cannot ask `--help`; it is the turn that must know what the app stores and how
(`docs/tree/dec-a-puntal-plans-in-one-turn-and-code-executes.md`: the puntal returns the operations
at once, so the knowledge it needs has to be in the brief it is given).

Every launch goes to the fake `claude`. Pure filesystem and subprocess. This file must not request
the `engine` or `db_sandbox` fixture.
"""

from __future__ import annotations

import json

import pytest
from puntal_support import (
    BENCH,
    drive,
    puntal_environment,  # noqa: F401  (the `environment` fixture)
    write_config,
)

pytestmark = pytest.mark.usefixtures("no_real_backend")

API_FILE = BENCH / "persistence_api.txt"
INTRODUCTION = "THE APP'S DATA API"


def fast(environment, *arguments, **keywords):
    return drive(environment, *arguments, path=None, **keywords)


def system_prompt_of_the_last_launch(tmp_path) -> str:
    argv = json.loads((tmp_path / "argv.log").read_text().splitlines()[-1])["argv"]
    return argv[argv.index("--system-prompt") + 1]


def with_api_file(environment, tmp_path, api_file: str):
    environment["AGENTS_CONFIG_PATH"] = str(
        write_config(tmp_path, puntal_section={"persistence_api_file": api_file})
    )


def test_the_fast_contract_carries_the_apps_data_api_when_one_is_configured(environment, tmp_path):
    with_api_file(environment, tmp_path, str(API_FILE))
    assert fast(environment, payload={"title": "x"}).returncode == 0
    contract = system_prompt_of_the_last_launch(tmp_path)
    assert INTRODUCTION in contract
    # The same text the slow path gets, with its placeholders answered.
    assert "`./state get <collection> <id>`: one document." in contract
    assert "__" not in contract
    assert "no tools" in contract


def test_the_introduction_says_the_api_is_reference_only_for_a_turn_with_no_tool(
    environment, tmp_path
):
    with_api_file(environment, tmp_path, str(API_FILE))
    assert fast(environment, payload={"title": "x"}).returncode == 0
    contract = system_prompt_of_the_last_launch(tmp_path)
    introduction = contract.split(INTRODUCTION)[1].split("\n\n")[0]
    assert "no tool" in introduction and "none of these commands" in introduction


def test_without_an_api_file_the_fast_contract_has_no_trace_of_it(environment, tmp_path):
    assert fast(environment, payload={"title": "x"}).returncode == 0
    contract = system_prompt_of_the_last_launch(tmp_path)
    assert INTRODUCTION not in contract and "./state" not in contract
    assert "\n\n\n" not in contract, "an unconfigured section must not leave a gap behind it"


def test_the_slow_contract_still_carries_the_api_without_the_fast_introduction(
    environment, tmp_path
):
    with_api_file(environment, tmp_path, str(API_FILE))
    assert drive(environment, payload={"title": "x"}).returncode == 0
    contract = system_prompt_of_the_last_launch(tmp_path)
    assert "`./state get <collection> <id>`: one document." in contract
    assert INTRODUCTION not in contract
