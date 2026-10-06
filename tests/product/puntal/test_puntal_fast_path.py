"""The fast path of `bin/puntal_task.sh`: the pre-helper loads the declared state, the model PLANS in
one turn with no tool, the executor applies the operations, and a rejected plan or an undeclared read
costs one more turn that the telemetry marks.

Every launch goes to the fake `claude` (`PUNTAL_CLAUDE_BIN`); the `no_real_backend` fixture is the
second wall. Pure filesystem and subprocess. This file must not request the `engine` or `db_sandbox`
fixture.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest
from puntal_support import (
    BOARD_NODE_FILE,
    NODE_FILE,
    STORE_CLI,
    drive,
    play,
    puntal_environment,  # noqa: F401  (the `environment` fixture)
    telemetry_of,
    write_config,
)

from agent_os.product import puntal
from agent_os.product.puntal.fast.pre_helper import split_node_declaration

pytestmark = pytest.mark.usefixtures("no_real_backend")


def node_declaring(tmp_path, source, reads, name="node.md"):
    path = tmp_path / name
    body = split_node_declaration(source.read_text()).slice_text
    path.write_text("---\nreads:\n" + "".join(f"  - {r}\n" for r in reads) + "---\n" + body)
    return path


def fast(environment, *arguments, **keywords):
    return drive(environment, *arguments, path=None, **keywords)


def store_dump(tmp_path):
    result = subprocess.run(
        [sys.executable, str(STORE_CLI), "--dir", str(tmp_path / "store"), "dump"],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


# --- the fast path ----------------------------------------------------------------------------


def test_the_puntal_plans_with_no_tool_and_the_executor_applies_it(environment, tmp_path):
    result = fast(environment, payload={"title": "Printer jams", "priority": "high"})
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"ok": True, "ticket_id": "T-1"}
    dump = store_dump(tmp_path)
    assert dump["tickets"]["T-1"]["title"] == "Printer jams"
    # Derived data is the app's: the executor recounted it, the puntal never wrote it.
    assert dump["summary"]["board"] == {"open": 1, "in_progress": 0, "resolved": 0, "total": 1}

    (record,) = telemetry_of(tmp_path)
    assert tuple(record) == puntal.TELEMETRY_FIELDS and record["schema"] == 2
    assert record["path"] == "fast" and record["slow_path_reason"] is None
    assert record["tool_calls"] == [] and record["init"]["tools"] == []
    assert [turn["kind"] for turn in record["turns"]] == ["plan"]
    assert record["plan"]["operations"] == 2 and record["plan"]["applied"] is True
    assert record["plan"]["retries"] == 0 and record["plan"]["bindings"] == {"n": 1}
    assert record["executor"] == {"ran": True, "ok": True, "crashed": False, "errors": []}
    assert record["latency_s"]["executor"] > 0 and record["latency_s"]["pre_helper"] is None
    assert record["response"] == result.stdout.strip()


def test_the_fast_turn_is_launched_with_no_tool_and_no_allow_rule(environment, tmp_path):
    assert fast(environment, payload={"title": "x"}).returncode == 0
    argv = json.loads((tmp_path / "argv.log").read_text().splitlines()[0])["argv"]
    assert "--tools=" in argv
    assert not [a for a in argv if a.startswith("--allowedTools")]
    system_prompt = argv[argv.index("--system-prompt") + 1]
    assert "no tools" in system_prompt and "./state" not in system_prompt


def test_the_state_a_node_declares_it_reads_is_loaded_into_the_brief_before_the_model_runs(
    environment, tmp_path
):
    assert fast(environment, payload={"title": "a"}).returncode == 0
    node = node_declaring(
        tmp_path, BOARD_NODE_FILE, ["list tickets", "get tickets {payload.id}"], "board.md"
    )
    result = fast(environment, node=node, action="show_board", payload={"id": "T-1"})
    assert result.returncode == 0, result.stderr
    brief = json.loads((tmp_path / "argv.log").read_text().splitlines()[-1])["argv"][-1]
    assert "# State loaded for this action" in brief and "## list tickets" in brief
    assert "## get tickets T-1" in brief and "---" not in brief.split("# Action")[0]
    record = telemetry_of(tmp_path)[-1]
    assert record["path"] == "fast", "everything was declared: no slow turn"
    assert record["declared_reads"]["declared"] == ["list tickets", "get tickets {payload.id}"]
    assert (record["declared_reads"]["ran"], record["declared_reads"]["failed"]) == (2, 0)
    assert record["latency_s"]["pre_helper"] > 0
    assert json.loads(result.stdout)["counts"]["total"] == 1


def test_a_read_the_node_did_not_declare_costs_one_more_turn_and_is_marked(environment, tmp_path):
    undeclared = tmp_path / "undeclared.md"
    undeclared.write_text(split_node_declaration(BOARD_NODE_FILE.read_text()).slice_text)
    result = fast(environment, node=undeclared, action="show_board", payload={})
    assert result.returncode == 0, result.stderr
    (record,) = telemetry_of(tmp_path)
    assert record["path"] == "slow"
    assert "list of tickets" in record["slow_path_reason"]
    assert [turn["kind"] for turn in record["turns"]] == ["plan", "slow"]
    assert [c["command"].split()[1] for c in record["tool_calls"]] == ["list"]
    # The two turns ran under two different contracts, and the record says which.
    first, second = (turn["prompt_digest"] for turn in record["turns"])
    assert first != second
    assert record["versions"]["method_version"]["prompt_digest"] == second


def test_a_plan_the_validator_rejects_gets_one_retry_turn(environment, tmp_path):
    environment["FAKE_PUNTAL_FAULT"] = "bad_plan_once"
    result = fast(environment, payload={"title": "x"})
    assert result.returncode == 0, result.stderr
    (record,) = telemetry_of(tmp_path)
    assert [turn["kind"] for turn in record["turns"]] == ["plan", "retry"]
    assert record["plan"]["retries"] == 1 and record["plan"]["applied"] is True
    (attempt,) = record["plan"]["attempts"]
    assert attempt["stage"] == "validation" and "upsert" in attempt["errors"][0]
    brief = json.loads((tmp_path / "argv.log").read_text().splitlines()[-1])["argv"][-1]
    assert "# Your previous plan was rejected" in brief and "upsert" in brief
    assert record["usage"]["total_tokens"] > record["turns"][0]["total_tokens"]


def test_a_second_invalid_plan_ends_the_invocation_with_nothing_applied(environment, tmp_path):
    bad = [{"op": "final", "text": json.dumps({"operations": [{"op": "upsert"}], "answer": "x"})}]
    play(tmp_path, environment, {"turns": [bad, bad]})
    result = fast(environment, payload={"title": "x"})
    assert result.returncode == puntal.EXIT_INVALID_PLAN and result.stdout == ""
    (record,) = telemetry_of(tmp_path)
    assert record["outcome"] == "invalid_plan" and "upsert" in record["outcome_detail"]
    assert len(record["turns"]) == 2 and record["executor"]["ran"] is False
    assert store_dump(tmp_path) == {"_counters": {}}


def test_an_executor_that_refuses_sends_its_reasons_back_for_one_retry(environment, tmp_path):
    environment["FAKE_PUNTAL_FAULT"] = "update_missing_ticket"
    node = node_declaring(tmp_path, BOARD_NODE_FILE, ["get tickets {payload.id}"])
    result = fast(
        environment,
        node=node,
        action="change_status",
        payload={"id": "T-404", "status": "in_progress"},
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["ok"] is False
    (record,) = telemetry_of(tmp_path)
    (attempt,) = record["plan"]["attempts"]
    assert attempt["stage"] == "executor" and "tickets/T-404" in attempt["errors"][0]
    assert [turn["kind"] for turn in record["turns"]] == ["plan", "retry"]


def test_an_executor_that_refuses_twice_ends_executor_failed_and_nothing_is_answered(
    environment, tmp_path
):
    plan = {
        "operations": [
            {"op": "update", "collection": "tickets", "id": "T-404", "changes": {"status": "x"}}
        ],
        "answer": "done",
    }
    turn = [{"op": "final", "text": json.dumps(plan)}]
    play(tmp_path, environment, {"turns": [turn, turn]})
    result = fast(environment, payload={})
    assert result.returncode == puntal.EXIT_EXECUTOR_FAILED and result.stdout == ""
    (record,) = telemetry_of(tmp_path)
    assert record["outcome"] == "executor_failed" and "T-404" in record["outcome_detail"]


def test_an_executor_that_crashes_is_not_retried(environment, tmp_path):
    environment["PUNTAL_EXECUTOR_COMMAND"] = f"{sys.executable} -c 'import sys; sys.exit(9)'"
    result = fast(environment, payload={"title": "x"})
    assert result.returncode == puntal.EXIT_EXECUTOR_FAILED
    (record,) = telemetry_of(tmp_path)
    assert len(record["turns"]) == 1 and record["executor"]["crashed"] is True
    assert "status 9" in record["outcome_detail"]


def test_a_tool_call_on_the_fast_path_is_a_contract_violation(environment, tmp_path):
    environment["FAKE_PUNTAL_FAULT"] = "write_code"
    result = fast(environment, node=BOARD_NODE_FILE, action="export_csv", payload={})
    assert result.returncode == puntal.EXIT_CONTRACT_VIOLATION and result.stdout == ""
    (record,) = telemetry_of(tmp_path)
    assert record["tool_violations"] == ["tool 'Write' on a turn that has no tools"]


def test_the_ceilings_bind_the_whole_invocation_not_each_turn(environment, tmp_path):
    bad = [{"op": "final", "text": "not json"}]
    play(tmp_path, environment, {"turns": [bad, bad]})
    environment["AGENTS_CONFIG_PATH"] = str(
        write_config(tmp_path, puntal_class={"max_total_tokens": 5500})
    )
    result = fast(environment, payload={})
    # The first turn alone spends more than half of 5500 and its retry has less than it needs.
    assert result.returncode in (puntal.EXIT_CEILING_CUT, puntal.EXIT_INVALID_PLAN)
    (record,) = telemetry_of(tmp_path)
    assert record["usage"]["total_tokens"] >= record["turns"][0]["total_tokens"]


def test_a_dry_run_shows_the_fast_launch_and_the_state_it_would_load(environment, tmp_path):
    node = node_declaring(tmp_path, BOARD_NODE_FILE, ["list tickets"])
    result = fast(environment, "--dry-run", node=node, action="show_board", payload={})
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "path:        fast" in out and "--tools=" in out and "--allowedTools" not in out
    assert "## list tickets" in out and "reads:       ['list tickets']" in out
    assert not (tmp_path / "argv.log").exists()


# --- configuration ----------------------------------------------------------------------------


def test_without_an_executor_the_fast_path_is_refused_before_anything_is_spent(
    environment, tmp_path
):
    del environment["PUNTAL_EXECUTOR_COMMAND"]
    result = fast(environment, payload={})
    assert result.returncode == puntal.EXIT_NOT_RUN and "executor" in result.stderr
    assert not (tmp_path / "argv.log").exists()


def test_a_read_that_is_not_one_is_never_run_by_the_pre_helper(environment, tmp_path):
    node = node_declaring(tmp_path, NODE_FILE, ["put tickets T-9 {}"])
    assert fast(environment, node=node, payload={"title": "x"}).returncode == 0
    assert not (tmp_path / "store" / "tickets" / "T-9.json").exists()
    assert "'put' is not a read" in " ".join(
        telemetry_of(tmp_path)[0]["declared_reads"]["problems"]
    )
