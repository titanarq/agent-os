"""`bin/puntal_task.sh` and `agent_os/puntal.py` -- the puntal driver: what it launches, what it
refuses, what it measures and what it logs.

Nothing here spends a turn. Every launch goes to `bench/puntal/fake_claude.py`, passed to the driver
through `PUNTAL_CLAUDE_BIN` (the per-backend override every driver has), and the `no_real_backend`
fixture puts a trap `claude` first on PATH as a second wall: the test fails if anything ever resolves
the bare name. The fake rejects a flag the real CLI's grammar does not have, so a driver that drifts
from it fails here and not in a measurement.

Pure filesystem and subprocess. This file must not request the `engine` or `db_sandbox` fixture.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

import pytest
import yaml
from conftest import EXAMPLE_CONFIG

from agent_os import guard as agent_guard
from agent_os import puntal
from agent_os.cli import AGENT_OS_DIR
from agent_os.lib import (
    PROMPTS_DIR,
    PuntalConfig,
    TaskClass,
    load_agents_config,
    load_role_class,
    render_prompt,
)

pytestmark = pytest.mark.usefixtures("no_real_backend")

DRIVER = AGENT_OS_DIR / "bin" / "puntal_task.sh"
BENCH = AGENT_OS_DIR / "bench" / "puntal"
FAKE = BENCH / "fake_claude.py"
STORE_CLI = BENCH / "store.py"
NODE_FILE = BENCH / "nodes" / "uc-1-file-a-ticket.md"
BOARD_NODE_FILE = BENCH / "nodes" / "uc-3-see-the-board.md"


def write_config(tmp_path, *, puntal_section=None, puntal_class=None, class_backend=None):
    data = yaml.safe_load(EXAMPLE_CONFIG.read_text())
    data["puntal"].update(puntal_section or {})
    data["classes"]["puntal"].update(puntal_class or {})
    if class_backend:
        data["classes"]["puntal"]["backend"] = class_backend
    path = tmp_path / "agents.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return path


@pytest.fixture
def environment(tmp_path):
    """The driver's launch path with every write moved under tmp_path, the fake as its backend and no
    latency: nothing real is reachable from a run in this fixture."""
    env = dict(os.environ)
    env.update(
        AGENTS_CONFIG_PATH=str(write_config(tmp_path)),
        AGENT_CACHE_DIR=str(tmp_path / "cache"),
        PUNTAL_CLAUDE_BIN=str(FAKE),
        PUNTAL_PERSISTENCE_COMMAND=f"{sys.executable} {STORE_CLI} --dir {tmp_path / 'store'}",
        FAKE_PUNTAL_LATENCY="0",
        FAKE_PUNTAL_STATE_DIR=str(tmp_path / "fake-state"),
        FAKE_PUNTAL_ARGV_LOG=str(tmp_path / "argv.log"),
        FAKE_PUNTAL_PID_FILE=str(tmp_path / "fake.pid"),
    )
    env.pop("FAKE_PUNTAL_FAULT", None)
    env.pop("FAKE_PUNTAL_PLAYBOOK", None)
    return env


def drive(environment, *arguments, node=NODE_FILE, action="create_ticket", payload=None):
    command = ["bash", str(DRIVER), "--action", action, "--node-file", str(node)]
    if payload is not None:
        command += ["--payload", json.dumps(payload)]
    return subprocess.run(
        [*command, *arguments], env=environment, capture_output=True, text=True, check=False
    )


def telemetry_of(tmp_path) -> list[dict]:
    path = tmp_path / "cache" / "telemetry.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def play(tmp_path, environment, steps):
    playbook = tmp_path / "playbook.json"
    playbook.write_text(json.dumps(steps))
    environment["FAKE_PUNTAL_PLAYBOOK"] = str(playbook)


# --- the launch -------------------------------------------------------------------------------


def test_dry_run_prints_the_launch_and_spends_nothing(environment, tmp_path):
    result = drive(environment, "--dry-run", payload={"title": "x"})
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "--safe-mode" in out
    assert "--tools=Bash" in out
    assert "--allowedTools=Bash(./state *)" in out
    assert "--permission-mode dontAsk" in out
    assert "--system-prompt" not in out  # printed under its own heading, not as a flag
    assert "--- contract (system prompt) ---" in out and "--- brief (first message) ---" in out
    assert not (tmp_path / "cache").exists(), "a dry run wrote into the cache"
    assert not (tmp_path / "argv.log").exists(), "a dry run launched the backend"


def test_a_run_hands_the_backend_exactly_the_confining_flags_and_a_scratch_directory(
    environment, tmp_path
):
    result = drive(environment, payload={"title": "Printer jams", "priority": "high"})
    assert result.returncode == 0, result.stderr
    call = json.loads((tmp_path / "argv.log").read_text().splitlines()[0])
    argv = call["argv"]
    for flag in ("-p", "--verbose", "--include-partial-messages", "--safe-mode"):
        assert flag in argv
    assert argv[argv.index("--permission-mode") + 1] == "dontAsk"
    # The variadic options are written with `=`: a space would let them swallow the prompt.
    assert "--tools=Bash" in argv and "--allowedTools=Bash(./state *)" in argv
    assert argv[argv.index("--output-format") + 1] == "stream-json"
    assert float(argv[argv.index("--max-budget-usd") + 1]) == 0.25
    assert argv[argv.index("--model") + 1] == "claude-sonnet-5-5"
    assert "--effort" not in argv
    # The contract is the system prompt; the LAST argument is the brief, the node slice in it.
    assert "PUNTAL" in argv[argv.index("--system-prompt") + 1]
    assert argv[-1].startswith("# Node UC-1: file a ticket") and "Printer jams" in argv[-1]
    assert call["environment"]["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] == "1"
    # The backend ran in a throwaway directory of its own, gone by now, and never in the checkout.
    assert pathlib.Path(call["cwd"]).name.startswith("agent-os-puntal-scratch.")
    assert not pathlib.Path(call["cwd"]).exists()


def test_effort_and_model_overrides_reach_the_backend(environment, tmp_path):
    result = drive(environment, "--effort", "low", "--model", "some-other-model", payload={})
    assert result.returncode == 0, result.stderr
    argv = json.loads((tmp_path / "argv.log").read_text().splitlines()[0])["argv"]
    assert argv[argv.index("--effort") + 1] == "low"
    assert argv[argv.index("--model") + 1] == "some-other-model"
    assert telemetry_of(tmp_path)[0]["model"] == "some-other-model"


# --- what an answered run leaves ---------------------------------------------------------------


def test_an_answered_run_prints_only_the_response_and_logs_everything(environment, tmp_path):
    result = drive(
        environment,
        "--session-id",
        "user-session-7",
        "--label",
        "stage=test",
        "--invocation-id",
        "inv-1",
        payload={"title": "Printer jams", "priority": "high"},
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"ok": True, "ticket_id": "T-1"}
    # The state really is in the persistence store, not in anyone's transcript.
    stored = json.loads((tmp_path / "store" / "tickets" / "T-1.json").read_text())
    assert stored["title"] == "Printer jams" and stored["priority"] == "high"

    (record,) = telemetry_of(tmp_path)
    assert tuple(record) == puntal.TELEMETRY_FIELDS
    assert record["schema"] == puntal.TELEMETRY_SCHEMA
    assert record["invocation_id"] == "inv-1" and record["session_id"] == "user-session-7"
    assert record["backend_session_id"].startswith("fake-")
    assert record["action"] == "create_ticket" and record["node"] == "uc-1-file-a-ticket"
    assert record["labels"] == {"stage": "test"}
    assert record["outcome"] == "ok" and record["exit_code"] == 0
    assert record["class"] == "puntal" and record["backend"] == "claude"
    assert record["response"] == result.stdout.strip()
    assert record["gap_note"] is None and record["tool_violations"] == []
    assert record["usage"]["total_tokens"] > 0 and record["cost_usd"] > 0
    assert [c["command"].split()[1] for c in record["tool_calls"]][:2] == ["next-id", "put"]
    assert record["init"]["tools"] == ["Bash"]
    first = record["usage"]["first_turn"]
    assert record["usage"]["context_tokens_first_turn"] == sum(
        first[k] for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
    )
    assert 0 < record["usage"]["context_tokens_first_turn"] < record["usage"]["context_tokens_peak"]
    assert record["scratch_extra_entries"] == []

    # Time-to-first-signal is measured from the click's arrival, and the milestones are in order.
    latency = record["latency_s"]
    assert (
        0
        < latency["python_startup"]
        <= latency["launch_overhead"]
        <= latency["first_event"]
        <= latency["first_message"]
        <= latency["first_text_delta"]
        <= latency["total"]
    )
    assert latency["first_message"] <= latency["first_tool_call"]
    assert latency["final_answer_first_delta"] == latency["first_text_delta"]

    # The class's own runs.tsv, with the columns every role's has, and the per-run log + marker.
    rows = (tmp_path / "cache" / "runs.tsv").read_text().splitlines()
    assert rows[0] == "ts\tcontext\tmodel\tnum_turns\ttotal_cost_usd"
    assert rows[1].split("\t")[1:3] == ["create_ticket @ uc-1-file-a-ticket", "claude-sonnet-5-5"]
    (log,) = (tmp_path / "cache").glob("*.log")
    assert (tmp_path / "cache" / f"{log.name}.exited").is_file()
    assert "backend:   claude" in log.read_text()


def test_the_guard_reads_a_puntal_run_log_like_any_roles(environment, tmp_path):
    """The log carries the `backend:` header line and the raw stream, so a puntal run is one more
    quota observation for the guard and needs no code of its own there."""
    assert drive(environment, payload={"title": "x"}).returncode == 0
    (log,) = (tmp_path / "cache").glob("*.log")
    assert agent_guard.role_run_quota_status(log) == "allowed"


def test_the_guard_counts_a_puntal_run_among_the_role_runs_it_reads_quota_from(
    environment, tmp_path, monkeypatch
):
    assert drive(environment, payload={"title": "x"}).returncode == 0
    monkeypatch.setenv("AGENT_CACHE_DIR", str(tmp_path / "cache"))
    observations = agent_guard.role_log_quota_observations(main=tmp_path)
    assert observations["claude"].status == "allowed"
    assert observations["claude"].log.parent == tmp_path / "cache"


def test_a_gap_note_is_split_from_the_response_and_kept_in_the_telemetry(environment, tmp_path):
    result = drive(environment, node=BOARD_NODE_FILE, action="export_csv", payload={})
    assert result.returncode == 0, result.stderr
    assert "GAP:" not in result.stdout and result.stdout.startswith("id,title")
    (record,) = telemetry_of(tmp_path)
    assert record["gap_note"] == "asked for a CSV export; the node does not describe it"
    assert "GAP:" not in record["response"]
    assert "gap note" in result.stderr


def test_concurrent_runs_never_interleave_their_telemetry(environment, tmp_path):
    processes = [
        subprocess.Popen(
            [
                "bash",
                str(DRIVER),
                "--action",
                "show_board",
                "--node-file",
                str(BOARD_NODE_FILE),
                "--invocation-id",
                f"parallel-{index}",
            ],
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for index in range(4)
    ]
    assert [p.wait(timeout=120) for p in processes] == [0, 0, 0, 0]
    assert sorted(r["invocation_id"] for r in telemetry_of(tmp_path)) == [
        f"parallel-{i}" for i in range(4)
    ]
    assert len((tmp_path / "cache" / "runs.tsv").read_text().splitlines()) == 5
    assert len(list((tmp_path / "cache").glob("*.log"))) == 4


# --- "the puntal never writes code": the cuts ---------------------------------------------------


def test_a_tool_other_than_bash_is_a_contract_violation_and_the_run_is_cut(environment, tmp_path):
    environment["FAKE_PUNTAL_FAULT"] = "write_code"
    result = drive(environment, node=BOARD_NODE_FILE, action="export_csv", payload={})
    assert result.returncode == puntal.EXIT_CONTRACT_VIOLATION
    assert result.stdout == "", "a cut run hands the app no response"
    (record,) = telemetry_of(tmp_path)
    assert record["outcome"] == "contract_violation"
    assert record["tool_violations"] == ["tool 'Write' is not the persistence tool"]
    assert record["tool_calls"][-1]["name"] == "Write"
    # The run was killed, not allowed to finish: no result event, and no process left behind.
    assert record["usage"]["turns"] is None
    assert not pathlib.Path(f"/proc/{(tmp_path / 'fake.pid').read_text()}").exists()


@pytest.mark.parametrize(
    "command",
    [
        "cat /etc/passwd",
        "ls",
        "./state get tickets T-1; rm -rf .",
        "./state get tickets T-1 && ./state get tickets T-2",
        "./state list tickets | head",
        "./state put a b c > somefile",
        "./state get x 2>&1",
        './state put a b "$(cat secret)"',
        "./state put a b `id`",
        "./state\nrm x",
        "./other get x",
        "python3 -c 'print(1)'",
        "",
    ],
)
def test_audit_refuses_anything_but_one_state_command(command):
    assert puntal.audit_tool_call("Bash", {"command": command}) is not None


@pytest.mark.parametrize(
    "command",
    [
        "./state get tickets T-1",
        "./state next-id ticket",
        "./state list tickets",
        './state put tickets T-1 \'{"title": "a | b; c & d $5", "n": 1}\'',
        './state update tickets T-1 \'{"status": "in_progress"}\'',
    ],
)
def test_audit_allows_the_state_command_with_quoted_arguments(command):
    assert puntal.audit_tool_call("Bash", {"command": command}) is None


def test_audit_refuses_any_other_tool_and_a_malformed_call():
    assert puntal.audit_tool_call("Write", {"file_path": "x"}) is not None
    assert puntal.audit_tool_call("Read", {}) is not None
    assert puntal.audit_tool_call("Bash", "not a mapping") is not None
    assert puntal.audit_tool_call("Bash", {"command": 7}) is not None


def test_a_bash_call_outside_the_state_command_cuts_the_run(environment, tmp_path):
    play(
        tmp_path,
        environment,
        [
            {"op": "tool", "command": "./state list tickets"},
            {"op": "tool_raw", "name": "Bash", "input": {"command": "cat /etc/hostname"}},
            {"op": "final", "text": "never reached"},
        ],
    )
    result = drive(environment, payload={})
    assert result.returncode == puntal.EXIT_CONTRACT_VIOLATION and result.stdout == ""
    (record,) = telemetry_of(tmp_path)
    assert record["outcome"] == "contract_violation"
    assert "cat /etc/hostname" in record["tool_violations"][0]
    assert len(record["tool_calls"]) == 2


def test_more_tool_calls_than_the_loop_guard_allows_cuts_the_run(environment, tmp_path):
    environment["AGENTS_CONFIG_PATH"] = str(
        write_config(tmp_path, puntal_section={"max_tool_calls": 2})
    )
    play(
        tmp_path,
        environment,
        [{"op": "tool", "command": "./state list tickets"}] * 5 + [{"op": "final", "text": "x"}],
    )
    result = drive(environment, payload={})
    assert result.returncode == puntal.EXIT_CEILING_CUT and result.stdout == ""
    (record,) = telemetry_of(tmp_path)
    assert record["outcome"] == "ceiling_cut" and "2 tool calls" in record["outcome_detail"]


def test_a_turn_past_max_context_cuts_the_run_before_it_finishes(environment, tmp_path):
    environment["FAKE_PUNTAL_FAULT"] = "runaway_context"
    result = drive(environment, payload={"title": "x"})
    assert result.returncode == puntal.EXIT_CEILING_CUT and result.stdout == ""
    (record,) = telemetry_of(tmp_path)
    assert record["outcome"] == "ceiling_cut" and "max_context=30000" in record["outcome_detail"]
    assert record["usage"]["context_tokens_peak"] > 30000 and record["usage"]["turns"] is None
    assert not (tmp_path / "store").exists(), "the run was cut before it touched the store"


def test_the_ceilings_come_from_the_puntal_class(environment, tmp_path):
    environment["AGENTS_CONFIG_PATH"] = str(
        write_config(tmp_path, puntal_class={"max_context": 123456, "max_cost_usd": 1.5})
    )
    assert drive(environment, payload={"title": "x"}).returncode == 0
    (record,) = telemetry_of(tmp_path)
    assert record["ceilings"]["max_context"] == 123456
    argv = json.loads((tmp_path / "argv.log").read_text().splitlines()[0])["argv"]
    assert float(argv[argv.index("--max-budget-usd") + 1]) == 1.5


def test_a_hung_backend_is_killed_by_the_safety_timeout(environment, tmp_path):
    environment["FAKE_PUNTAL_FAULT"] = "hang"
    result = drive(environment, "--timeout", "2", payload={})
    assert result.returncode == puntal.EXIT_TIMEOUT and result.stdout == ""
    (record,) = telemetry_of(tmp_path)
    assert record["outcome"] == "timeout" and 2 <= record["latency_s"]["total"] < 30
    assert not pathlib.Path(f"/proc/{(tmp_path / 'fake.pid').read_text()}").exists()


def test_a_backend_that_reports_an_error_is_an_error_with_no_response(environment, tmp_path):
    play(
        tmp_path,
        environment,
        [
            {"op": "text", "text": "I will try."},
            {"op": "final", "text": "boom", "subtype": "error_during_execution", "is_error": True},
        ],
    )
    result = drive(environment, payload={})
    assert result.returncode == puntal.EXIT_BACKEND_FAILED and result.stdout == ""
    (record,) = telemetry_of(tmp_path)
    assert record["outcome"] == "error" and "error_during_execution" in record["outcome_detail"]


def test_a_backend_that_dies_with_noise_and_no_result_keeps_the_noise(environment, tmp_path):
    play(
        tmp_path,
        environment,
        [{"op": "raw", "line": "error: something broke"}, {"op": "exit", "code": 3}],
    )
    result = drive(environment, payload={})
    assert result.returncode == puntal.EXIT_BACKEND_FAILED
    (record,) = telemetry_of(tmp_path)
    assert record["outcome"] == "error" and "something broke" in record["outcome_detail"]
    assert record["stderr_tail"] == ["error: something broke"]
    # It still leaves its row, whatever its outcome: a missing row would read as "never happened".
    assert len((tmp_path / "cache" / "runs.tsv").read_text().splitlines()) == 2


def test_a_missing_backend_binary_is_an_error_not_a_traceback(environment, tmp_path):
    environment["PUNTAL_CLAUDE_BIN"] = str(tmp_path / "no-such-binary")
    result = drive(environment, payload={})
    assert result.returncode == puntal.EXIT_BACKEND_FAILED
    assert "Traceback" not in result.stderr
    (record,) = telemetry_of(tmp_path)
    assert record["outcome"] == "error" and "could not start" in record["outcome_detail"]


def test_a_file_left_in_the_scratch_directory_is_recorded(environment, tmp_path):
    play(
        tmp_path,
        environment,
        [{"op": "write_file", "path": "export.py"}, {"op": "final", "text": "{}"}],
    )
    assert drive(environment, payload={}).returncode == 0
    assert telemetry_of(tmp_path)[0]["scratch_extra_entries"] == ["export.py"]


# --- what it refuses to run --------------------------------------------------------------------


def test_it_refuses_without_a_persistence_command_and_writes_nothing(environment, tmp_path):
    del environment["PUNTAL_PERSISTENCE_COMMAND"]
    result = drive(environment, payload={})
    assert result.returncode == puntal.EXIT_NOT_RUN and result.stdout == ""
    assert "no persistence command" in result.stderr and "founding decision 4" in result.stderr
    assert not (tmp_path / "cache").exists() and not (tmp_path / "argv.log").exists()


def test_the_persistence_command_can_come_from_config(environment, tmp_path):
    del environment["PUNTAL_PERSISTENCE_COMMAND"]
    environment["AGENTS_CONFIG_PATH"] = str(
        write_config(
            tmp_path,
            puntal_section={
                "persistence_command": f"{sys.executable} {STORE_CLI} --dir {tmp_path / 'from-config'}"
            },
        )
    )
    assert drive(environment, payload={"title": "x"}).returncode == 0
    assert (tmp_path / "from-config" / "tickets" / "T-1.json").is_file()


@pytest.mark.parametrize("missing", ["node", "empty-node", "payload-both"])
def test_it_refuses_an_unusable_request(environment, tmp_path, missing):
    empty = tmp_path / "empty.md"
    empty.write_text("  \n")
    if missing == "node":
        result = drive(environment, node=tmp_path / "absent.md")
    elif missing == "empty-node":
        result = drive(environment, node=empty)
    else:
        result = drive(environment, "--payload-file", str(empty), payload={})
    assert result.returncode == puntal.EXIT_NOT_RUN and result.stdout == ""
    assert "puntal not run" in result.stderr
    assert not (tmp_path / "argv.log").exists()


def test_it_refuses_a_puntal_class_on_a_backend_whose_stream_it_cannot_confine(
    environment, tmp_path
):
    environment["AGENTS_CONFIG_PATH"] = str(write_config(tmp_path, class_backend="qwen"))
    result = drive(environment, payload={})
    assert result.returncode == puntal.EXIT_NOT_RUN
    assert "qwen_jsonl" in result.stderr and not (tmp_path / "argv.log").exists()


def test_it_refuses_a_config_that_does_not_load(environment, tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("project: [not, a, mapping]\n")
    environment["AGENTS_CONFIG_PATH"] = str(bad)
    result = drive(environment, payload={})
    assert result.returncode == puntal.EXIT_NOT_RUN and "does not load" in result.stderr


def test_a_payload_that_looks_like_a_placeholder_cannot_rewrite_the_brief(environment):
    result = drive(environment, "--dry-run", payload={"title": "__NODE__ __TEST_COMMAND__"})
    assert result.returncode == 0, result.stderr
    assert '"title": "__NODE__ __TEST_COMMAND__"' in result.stdout


def test_the_node_slice_and_payload_can_come_from_stdin(environment, tmp_path):
    result = subprocess.run(
        [
            "bash",
            str(DRIVER),
            "--action",
            "show_board",
            "--node-file",
            "-",
            "--node-id",
            "from-stdin",
        ],
        input="# Node X\nList nothing.\n",
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert telemetry_of(tmp_path)[0]["node"] == "from-stdin"


# --- the stream observer, on canned events -----------------------------------------------------

CEILINGS = puntal.Ceilings(
    max_context=30000,
    max_cost_usd=0.25,
    max_total_tokens=300000,
    max_tool_calls=5,
    timeout_seconds=9,
)


def partial(event):
    return {"type": "stream_event", "event": event}


def feed(observer, event, at_s):
    """One event as the driver delivers it: a raw line, stamped on arrival."""
    return observer.observe_line(json.dumps(event), at_s)


def test_time_to_first_signal_is_the_first_text_delta_of_any_message():
    observer = puntal.StreamObserver(CEILINGS)
    feed(observer, {"type": "system", "subtype": "init", "tools": ["Bash"]}, 0.5)
    feed(observer, partial({"type": "message_start", "message": {"id": "m1", "usage": {}}}), 0.9)
    feed(
        observer,
        partial(
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": "I will look."},
            }
        ),
        1.2,
    )
    feed(observer, partial({"type": "message_start", "message": {"id": "m2", "usage": {}}}), 2.0)
    feed(
        observer,
        partial(
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": "{}"},
            }
        ),
        2.6,
    )
    feed(
        observer,
        {
            "type": "assistant",
            "message": {"id": "m1", "content": [{"type": "text", "text": "I will look."}]},
        },
        2.7,
    )
    feed(
        observer,
        {"type": "assistant", "message": {"id": "m2", "content": [{"type": "text", "text": "{}"}]}},
        2.8,
    )
    assert observer.first_event_s == 0.5
    assert observer.first_message_s == 0.9
    assert observer.first_text_delta_s == 1.2, "the first signal is the narration, not the answer"
    assert observer.final_answer_first_delta_s() == 2.6, "the answer's own first delta is separate"


def test_without_partial_messages_there_is_no_first_delta_and_the_answer_still_comes_through():
    observer = puntal.StreamObserver(CEILINGS)
    feed(
        observer,
        {"type": "assistant", "message": {"id": "m1", "content": [{"type": "text", "text": "hi"}]}},
        1.0,
    )
    feed(observer, {"type": "result", "subtype": "success", "is_error": False, "result": "hi"}, 1.5)
    assert observer.first_text_delta_s is None
    assert observer.final_text() == "hi"


def test_a_tool_input_is_audited_when_its_block_closes_not_when_the_message_ends():
    observer = puntal.StreamObserver(CEILINGS)
    feed(observer, partial({"type": "message_start", "message": {"id": "m1", "usage": {}}}), 0.1)
    feed(
        observer,
        partial(
            {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "tool_use", "id": "t1", "name": "Bash"},
            }
        ),
        0.2,
    )
    assert (
        feed(
            observer,
            partial(
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "input_json_delta", "partial_json": '{"command": "rm -rf'},
                }
            ),
            0.3,
        )
        is None
    )
    feed(
        observer,
        partial(
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "input_json_delta", "partial_json": ' /"}'},
            }
        ),
        0.4,
    )
    cut = feed(observer, partial({"type": "content_block_stop", "index": 0}), 0.5)
    assert cut is not None and cut[0] == "contract_violation"


def test_usage_is_counted_once_per_message_however_many_events_repeat_it():
    observer = puntal.StreamObserver(CEILINGS)
    usage = {"input_tokens": 10, "cache_read_input_tokens": 1000, "output_tokens": 5}
    for _ in range(3):  # the CLI repeats a message's usage on every content block's event
        feed(
            observer,
            {"type": "assistant", "message": {"id": "m1", "usage": usage, "content": []}},
            1.0,
        )
    assert observer.running_total_tokens() == 1015 and observer.peak_context_tokens() == 1010


@pytest.mark.parametrize(
    "text, response, gap",
    [
        ('{"ok": true}', '{"ok": true}', None),
        (
            '{"ok": true}\nGAP: asked for X; the node does not describe it',
            '{"ok": true}',
            "asked for X; the node does not describe it",
        ),
        ("a\nGAP: first\nb\nGAP: second", "a\nGAP: first\nb", "second"),
        ("answer\n  GAP:   \n", "answer", None),
        ("", "", None),
    ],
)
def test_split_gap_note(text, response, gap):
    assert puntal.split_gap_note(text) == (response, gap)


def test_the_state_shim_runs_the_persistence_command_from_the_hosts_root(tmp_path):
    host = tmp_path / "host"
    scratch = tmp_path / "scratch"
    host.mkdir()
    scratch.mkdir()
    (host / "app-state.sh").write_text('#!/bin/sh\necho "cwd=$(pwd) args=$*"\n')
    (host / "app-state.sh").chmod(0o755)
    puntal.write_state_shim(scratch, host, ["./app-state.sh", "--fixed"])
    ran = subprocess.run(
        [str(scratch / "state"), "get", "a b"],
        cwd=scratch,
        capture_output=True,
        text=True,
        check=True,
    )
    assert ran.stdout.strip() == f"cwd={host} args=--fixed get a b"


# --- the contract and the class ---------------------------------------------------------------


def test_the_contract_template_renders_with_its_placeholders_answered():
    text = render_prompt(
        "puntal",
        {"PERSISTENCE_API": "- `__STATE_COMMAND__ get <c> <id>`", "STATE_COMMAND": "./state"},
    )
    assert "`./state get <c> <id>`" in text and "__" not in text
    assert "never write" in text.lower() or "never writes" in text.lower()
    assert "GAP:" in text


def test_the_contract_carries_the_hosts_extension_point_and_names_no_host_script():
    template = (PROMPTS_DIR / "puntal.md").read_text()
    assert "__PROJECT_EXTRAS__" in template
    assert "scripts/" not in template


def test_the_example_config_has_exactly_one_puntal_class_with_per_invocation_ceilings():
    name, task_class = load_role_class("puntal", EXAMPLE_CONFIG)
    assert name == "puntal" and task_class.backend == "claude"
    assert task_class.max_context <= 50000 and task_class.max_cost_usd <= 0.5
    assert task_class.fallback is None and task_class.escalate is None


def test_a_puntal_class_cannot_declare_a_fallback():
    fields = {
        "role": "puntal",
        "backend": "claude",
        "model": "m",
        "max_context": 1,
        "max_cost_usd": 1.0,
        "max_total_tokens": 1,
        "commit_warn_turns": 1,
        "commit_cut_turns": 2,
    }
    TaskClass(**fields)
    with pytest.raises(ValueError, match="never substitutes"):
        TaskClass(**fields, fallback={"backend": "qwen", "model": "q"})


def test_the_puntal_section_defaults_and_validation():
    defaults = PuntalConfig()
    assert (defaults.persistence_command, defaults.timeout_seconds, defaults.max_tool_calls) == (
        "",
        90,
        12,
    )
    assert load_agents_config(EXAMPLE_CONFIG).puntal == defaults
    with pytest.raises(ValueError):
        PuntalConfig(timeout_seconds=0)
    with pytest.raises(ValueError):
        PuntalConfig(unknown_key=1)
