"""Who acts: the interface of a puntal carries the actor to every command the driver runs for a click.

The app's code -- the pre-helper's reads, the executor, and the slow path's `./state` tool -- needs
to know who clicked, and the plan the model returns cannot say it. The contract is one environment
variable, `PUNTAL_ACTOR`: the JSON request's `actor` sets it, else what the caller already exported
is passed on untouched, else it is not set (`docs/AGENT_OS.md` §4.7).

Every launch goes to the fake `claude`. Pure filesystem and subprocess. This file must not request
the `engine` or `db_sandbox` fixture.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest
from puntal_support import (
    BOARD_NODE_FILE,
    DRIVER,
    EXECUTOR_CLI,
    NODE_FILE,
    STORE_CLI,
    puntal_environment,  # noqa: F401  (the `environment` fixture)
)

from agent_os.product.puntal.fast.pre_helper import split_node_declaration

pytestmark = pytest.mark.usefixtures("no_real_backend")

NOT_SET = "(not set)"

# The app's commands, as a host would write them: here, the bench's store and executor behind a
# wrapper that records the `PUNTAL_ACTOR` each call was started with.
RECORDING_WRAPPER = f"""\
import os, sys
log, program, *arguments = sys.argv[1:]
with open(log, "a") as handle:
    handle.write(os.environ.get("PUNTAL_ACTOR", "{NOT_SET}") + "\\n")
os.execv(sys.executable, [sys.executable, program, *arguments])
"""


@pytest.fixture(name="recorded")
def commands_that_record_the_actor(environment, tmp_path):
    """Replaces the persistence and executor commands of `environment`; returns where each one logs."""
    wrapper = tmp_path / "record_actor.py"
    wrapper.write_text(RECORDING_WRAPPER)
    store_dir = tmp_path / "store"
    logs = {"state": tmp_path / "state_actor.log", "executor": tmp_path / "executor_actor.log"}
    environment["PUNTAL_PERSISTENCE_COMMAND"] = (
        f"{sys.executable} {wrapper} {logs['state']} {STORE_CLI} --dir {store_dir}"
    )
    environment["PUNTAL_EXECUTOR_COMMAND"] = (
        f"{sys.executable} {wrapper} {logs['executor']} {EXECUTOR_CLI} --dir {store_dir}"
    )
    environment.pop("PUNTAL_ACTOR", None)
    return logs


def actors_logged(log) -> list[str]:
    return log.read_text().split("\n")[:-1] if log.exists() else []


def node_that_reads_the_board(tmp_path):
    path = tmp_path / "board.md"
    body = split_node_declaration(BOARD_NODE_FILE.read_text()).slice_text
    path.write_text("---\nreads:\n  - list tickets\n---\n" + body)
    return path


def json_call(environment, request, *flags):
    return subprocess.run(
        ["bash", str(DRIVER), "--json", *flags],
        input=json.dumps(request),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def create_ticket_request(**fields):
    return {
        "action": "create_ticket",
        "node": NODE_FILE.read_text(),
        "node_id": "uc-1",
        "payload": {"title": "By someone"},
        **fields,
    }


def test_the_requests_actor_reaches_the_executor(environment, recorded):
    result = json_call(environment, create_ticket_request(actor="ana"))
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["applied"] is True
    assert actors_logged(recorded["executor"]) == ["ana"]


def test_the_requests_actor_reaches_the_reads_the_node_declares(environment, recorded, tmp_path):
    node = node_that_reads_the_board(tmp_path)
    request = {"action": "show_board", "node": node.read_text(), "node_id": "uc-3", "payload": {}}
    result = json_call(environment, {**request, "actor": "ana"})
    assert result.returncode == 0, result.stderr
    assert actors_logged(recorded["state"]) == ["ana"]


def test_the_requests_actor_reaches_the_slow_paths_state_tool(environment, recorded):
    result = json_call(environment, create_ticket_request(actor="ana"), "--path", "slow")
    assert result.returncode == 0, result.stderr
    assert actors_logged(recorded["state"]), (
        "the slow path's tool calls ran the persistence command"
    )
    assert set(actors_logged(recorded["state"])) == {"ana"}


def test_an_actor_the_caller_exported_is_passed_on_when_the_request_names_none(
    environment, recorded
):
    environment["PUNTAL_ACTOR"] = "from-the-shell"
    result = json_call(environment, create_ticket_request())
    assert result.returncode == 0, result.stderr
    assert actors_logged(recorded["executor"]) == ["from-the-shell"]
    slow = json_call(environment, create_ticket_request(), "--path", "slow")
    assert slow.returncode == 0, slow.stderr
    assert set(actors_logged(recorded["state"])) == {"from-the-shell"}


def test_the_requests_actor_wins_over_an_exported_one(environment, recorded):
    environment["PUNTAL_ACTOR"] = "from-the-shell"
    assert json_call(environment, create_ticket_request(actor="ana")).returncode == 0
    assert actors_logged(recorded["executor"]) == ["ana"]


def test_with_no_actor_anywhere_the_variable_is_not_set(environment, recorded):
    assert json_call(environment, create_ticket_request()).returncode == 0
    assert actors_logged(recorded["executor"]) == [NOT_SET]


@pytest.mark.parametrize("actor", [42, ["ana"], {"name": "ana"}, "a\x00b"])
def test_an_actor_that_is_not_text_is_refused_before_anything_runs(environment, recorded, actor):
    result = json_call(environment, create_ticket_request(actor=actor))
    assert result.returncode == 2
    envelope = json.loads(result.stdout)
    assert envelope["outcome"] == "not_run" and "actor" in envelope["detail"]
    assert actors_logged(recorded["executor"]) == []


def test_an_actor_with_spaces_quotes_and_shell_syntax_arrives_exactly_as_written(
    environment, recorded
):
    actor = "Ana O'Brien $HOME `id` ; (x)"
    assert json_call(environment, create_ticket_request(actor=actor)).returncode == 0
    assert actors_logged(recorded["executor"]) == [actor]
    slow = json_call(environment, create_ticket_request(actor=actor), "--path", "slow")
    assert slow.returncode == 0, slow.stderr
    assert set(actors_logged(recorded["state"])) == {actor}
