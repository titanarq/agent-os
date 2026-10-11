"""The puntal's shell API and its feedback: JSON in and out for a host's shell in any stack, the plan
handed back unapplied for an app that applies it itself, and the owner's verdict recorded against the
invocation with the versions it was made under.

Every launch goes to the fake `claude`. Pure filesystem and subprocess. This file must not request the
`engine` or `db_sandbox` fixture.
"""

from __future__ import annotations

import json
import subprocess

import pytest
from puntal_support import (
    BENCH,
    BOARD_NODE_FILE,
    DRIVER,
    NODE_FILE,
    STORE_CLI,
    drive,
    puntal_environment,  # noqa: F401  (the `environment` fixture)
    telemetry_of,
)

from agent_os.product import puntal
from agent_os.product.puntal.telemetry.feedback import FEEDBACK_FIELDS
from agent_os.product.records.versions import prompt_digest

pytestmark = pytest.mark.usefixtures("no_real_backend")


def fast(environment, *arguments, **keywords):
    return drive(environment, *arguments, path=None, **keywords)


def store_dump(tmp_path):
    import sys

    result = subprocess.run(
        [sys.executable, str(STORE_CLI), "--dir", str(tmp_path / "store"), "dump"],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


# --- the generic API --------------------------------------------------------------------------


def json_call(environment, request, *flags):
    return subprocess.run(
        ["bash", str(DRIVER), "--json", *flags],
        input=json.dumps(request),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def request_for(node, **fields):
    return {
        "action": "create_ticket",
        "node": node.read_text(),
        "node_id": "uc-1",
        "payload": {"title": "From the shell"},
        **fields,
    }


def test_the_shell_api_takes_one_json_request_and_answers_one_envelope(environment, tmp_path):
    result = json_call(environment, request_for(NODE_FILE, invocation_id="shell-1", state="x"))
    assert result.returncode == 0, result.stderr
    envelope = json.loads(result.stdout)
    assert envelope["invocation_id"] == "shell-1" and envelope["outcome"] == "ok"
    assert envelope["answer"] == {"ok": True, "ticket_id": "T-1"}
    assert envelope["applied"] is True and envelope["path"] == "fast"
    assert [op["op"] for op in envelope["operations"]] == ["allocate", "put"]
    assert envelope["bindings"] == {"n": 1} and envelope["exit_status"] == 0
    assert telemetry_of(tmp_path)[0]["invocation_id"] == "shell-1"


def test_plan_only_hands_the_operations_back_unapplied_for_the_app_to_apply(environment, tmp_path):
    del environment["PUNTAL_EXECUTOR_COMMAND"]
    result = json_call(environment, request_for(NODE_FILE), "--plan-only")
    assert result.returncode == 0, result.stderr
    envelope = json.loads(result.stdout)
    assert envelope["applied"] is False and envelope["bindings"] == {}
    assert envelope["answer"] == {"ok": True, "ticket_id": "T-{{n}}"}
    assert envelope["operations"][0] == {"op": "allocate", "counter": "ticket", "bind": "n"}
    assert store_dump(tmp_path) == {"_counters": {}}


def test_the_shell_api_declares_reads_in_the_request_too(environment, tmp_path):
    request = request_for(BOARD_NODE_FILE, action="show_board", reads=["list tickets"], payload={})
    result = json_call(environment, request)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["path"] == "fast"


def test_a_bad_request_is_an_envelope_with_not_run(environment):
    for request in ({}, {"action": "a"}, {"action": "a", "node": "n"}, [1]):
        result = json_call(environment, request)
        assert result.returncode == puntal.EXIT_NOT_RUN
        assert json.loads(result.stdout)["outcome"] == "not_run"


def test_a_retry_the_app_asks_for_carries_what_it_rejected(environment, tmp_path):
    request = request_for(
        NODE_FILE,
        retry_of="inv-0",
        previous_attempt={"plan": {"operations": [], "answer": "no"}, "errors": ["not enough"]},
    )
    assert json_call(environment, request).returncode == 0
    brief = json.loads((tmp_path / "argv.log").read_text().splitlines()[-1])["argv"][-1]
    assert "Your previous plan was rejected" in brief and "not enough" in brief
    assert telemetry_of(tmp_path)[0]["labels"] == {"retry_of": "inv-0"}


# --- feedback ---------------------------------------------------------------------------------


def feedback(environment, *arguments):
    return subprocess.run(
        ["bash", str(DRIVER), "feedback", *arguments],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_feedback_is_recorded_against_the_invocation_with_its_versions(environment, tmp_path):
    assert fast(environment, "--invocation-id", "inv-7", payload={"title": "x"}).returncode == 0
    accepted = feedback(
        environment, "--invocation-id", "inv-7", "--verdict", "reject", "--note", "wrong priority"
    )
    assert accepted.returncode == 0, accepted.stderr
    lines = (tmp_path / "cache" / "feedback.jsonl").read_text().splitlines()
    (record,) = [json.loads(line) for line in lines]
    assert record["invocation_id"] == "inv-7" and record["verdict"] == "reject"
    assert record["note"] == "wrong priority" and record["action"] == "create_ticket"
    telemetry = telemetry_of(tmp_path)[0]
    assert record["versions"] == telemetry["versions"]
    assert record["versions"]["model"] == "claude-haiku-5-5"
    assert record["versions"]["cli_version"] == "fake-0"
    fast_contract = (BENCH.parent.parent / "prompts" / "puntal.md").read_text()
    assert record["versions"]["method_version"]["prompt_digest"] != prompt_digest(fast_contract), (
        "the digest is of the RENDERED prompt, extension point filled"
    )
    assert tuple(record) == FEEDBACK_FIELDS


def test_a_retry_verdict_can_name_the_invocation_that_replaced_it(environment, tmp_path):
    assert fast(environment, "--invocation-id", "inv-8", payload={"title": "x"}).returncode == 0
    result = feedback(
        environment, "--invocation-id", "inv-8", "--verdict", "retry", "--retried-as", "inv-9"
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["retried_as"] == "inv-9"


def test_feedback_on_an_invocation_nobody_recorded_is_refused_and_writes_nothing(
    environment, tmp_path
):
    result = feedback(environment, "--invocation-id", "ghost", "--verdict", "accept")
    assert result.returncode == puntal.EXIT_NOT_RUN and "ghost" in result.stderr
    assert not (tmp_path / "cache" / "feedback.jsonl").exists()


def test_a_verdict_that_is_not_one_is_refused(environment):
    assert feedback(environment, "--invocation-id", "x", "--verdict", "maybe").returncode == 2
