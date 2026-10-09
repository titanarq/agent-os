"""A run the backend refused on quota before it produced one event is a QUOTA cut (stage1i, #2).

On the vector host a worker relaunched while the account had no quota died at once with an empty
event stream, and the driver recorded `CUT_BY_GUARD reason=no_stage_commit` -- the symptom, where
the cause was `reason=quota`. The planner reads the reason: a quota cut waits for the window (or
redispatches on the class's fallback), a `no_stage_commit` cut is a worker that failed its stage and
may be escalated to a stronger model. Pure filesystem and subprocess: the driver's `stage-exit` is
called directly with the files the dead run left, and no backend is ever launched.
"""

from __future__ import annotations

import json
import subprocess

import pytest
from test_worker_task import DRIVER, ROOT, _staged_environment

from agent_os.streams.claude_jsonl import silent_run_quota_refusal

SESSION_LIMIT_LINE = "You've hit your session limit · resets 5:20pm (Europe/Madrid)"
REJECTED_RATE_LIMIT_EVENT = json.dumps(
    {"type": "rate_limit_event", "rate_limit_info": {"status": "rejected", "unifiedWindows": {}}}
)


def _stage_exit(tmp_path, *, events_text, log_text, backend_status):
    environment, cache, _worktree, _tmp = _staged_environment(
        tmp_path,
        stage_titles=("Write the failing test", "Make it pass"),
        mode="hang",
    )
    (cache / "worker_claude.issue").write_text("347\n")
    (cache / "worker_claude.stage").write_text("0/2\n")
    (cache / "worker_claude.jsonl").write_text(events_text)
    (cache / "worker_claude.log").write_text(log_text)
    environment = {**environment, "WORKER_BACKEND_STATUS": str(backend_status)}
    result = subprocess.run(
        ["bash", str(DRIVER), "claude", "stage-exit"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    state = (cache / "worker_claude.state").read_text().splitlines()[0]
    return result, state


@pytest.mark.parametrize("backend_status", [0, 1])
def test_a_run_with_no_event_whose_log_says_session_limit_is_a_quota_cut(tmp_path, backend_status):
    result, state = _stage_exit(
        tmp_path,
        events_text="",
        log_text=f"{SESSION_LIMIT_LINE}\n",
        backend_status=backend_status,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert state == "CUT_BY_GUARD reason=quota", (state, result.stdout)
    assert "quota" in result.stdout


def test_a_refusal_the_backend_printed_instead_of_an_event_is_a_quota_cut(tmp_path):
    """Claude Code can write its refusal as a plain line on stdout, which is the event file: the
    file is not empty, and not one line of it is an event."""
    _result, state = _stage_exit(
        tmp_path, events_text=f"{SESSION_LIMIT_LINE}\n", log_text="", backend_status=1
    )
    assert state == "CUT_BY_GUARD reason=quota", state


def test_a_rejected_rate_limit_event_without_a_stage_commit_is_a_quota_cut(tmp_path):
    """The stream itself says so, which is the authority the ADR names; it must outrank the
    stage that merely did not commit."""
    _result, state = _stage_exit(
        tmp_path, events_text=f"{REJECTED_RATE_LIMIT_EVENT}\n", log_text="", backend_status=1
    )
    assert state == "CUT_BY_GUARD reason=quota", state


def test_a_silent_run_whose_log_says_nothing_about_quota_is_still_a_failed_launch(tmp_path):
    _result, state = _stage_exit(
        tmp_path, events_text="", log_text="boom: unexpected flag --model\n", backend_status=1
    )
    assert state.startswith("FAILED_LAUNCH"), state


def test_a_clean_exit_with_events_and_no_quota_signal_stays_a_no_stage_commit_cut(tmp_path):
    event = json.dumps({"type": "system", "subtype": "init"})
    _result, state = _stage_exit(tmp_path, events_text=f"{event}\n", log_text="", backend_status=0)
    assert state == "CUT_BY_GUARD reason=no_stage_commit", state


@pytest.mark.parametrize(
    "text",
    [
        SESSION_LIMIT_LINE,
        "Claude usage limit reached. Your limit will reset at 3pm",
        'API Error: 429 {"type":"error","error":{"type":"rate_limit_error"}}',
        "error: status 429 too many requests",
    ],
)
def test_the_refusal_shapes_claude_code_prints_are_recognised(text):
    assert silent_run_quota_refusal(text) is not None


@pytest.mark.parametrize(
    "text",
    ["", "claude: command not found", "wrote 4290 bytes", "boom: unexpected flag --model"],
)
def test_other_output_is_not_a_quota_refusal(text):
    assert silent_run_quota_refusal(text) is None
