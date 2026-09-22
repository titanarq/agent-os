"""A role's own rejection reaches the quota verdict the launch gate reads (#429).

The verdict file `agent_guard_<backend>.json` has one writer, the guard module: the worker path in
`_tick_backend` and `fold_role_quota_observations`, which reads the logs the roles leave under
`.cache/<role>/`. It runs at the start of `tick` and of `_wake_locked`, and every role launch only
reads the file. The verdict is still the backend's own record, read by the worker path's detector
(`quota_status`), never an agent's words about itself
(docs/adr/2026-09-14-quota-exhaustion-is-read-from-the-backend-not-claimed-by-the-agent.md).

Pure filesystem. This file must not request the `engine` or `db_sandbox` fixture.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from agent_os import guard as agent_guard
from agent_os.lib import (
    load_mechanism,
    load_role_class,
    read_persisted_quota_verdict,
    role_launch,
)

TTL_SECONDS = load_mechanism().quota_verdict_ttl_minutes * 60
ROLE = "planner"
ROLE_BACKEND = load_role_class(ROLE)[1].backend


@pytest.fixture(autouse=True)
def _no_cache_overrides(monkeypatch):
    for name in ("AGENT_CACHE_DIR", "PLANNER_CACHE_DIR", "WORKER_CACHE_DIR"):
        monkeypatch.delenv(name, raising=False)


def _cache(main: Path) -> Path:
    return main / ".cache"


def _header(backend_line: str | None) -> list[str]:
    lines = ["ts:        20260918T084846Z", f"role:      {ROLE} (class {ROLE})"]
    if backend_line is not None:
        lines.append(f"backend:   {backend_line}")
    lines.append("model:     some-model")
    return lines


def _assistant(text: str = "", tokens: int = 10) -> dict:
    return {
        "type": "assistant",
        "session_id": "s1",
        "message": {
            "content": [{"type": "text", "text": text}],
            "usage": {"input_tokens": tokens, "output_tokens": tokens},
        },
    }


def _rejected_rate_limit_event() -> dict:
    return {
        "type": "rate_limit_event",
        "session_id": "s1",
        "rate_limit_info": {
            "status": "rejected",
            "unifiedWindows": {"five_hour": {"utilization": 1, "resetsAt": 1789727400}},
        },
    }


def _result(**fields) -> dict:
    event = {"type": "result", "subtype": "success", "is_error": False, "num_turns": 1}
    event.update(fields)
    return event


# The shape `.cache/planner/20260918T084846Z.log` actually carries: one rejected rate-limit event,
# an empty turn, and an error result with the backend's HTTP status.
REJECTED_RUN = [
    _rejected_rate_limit_event(),
    _assistant("", tokens=0),
    _result(
        is_error=True,
        api_error_status=429,
        terminal_reason="api_error",
        result="You've hit your session limit · resets 12:30pm",
    ),
]
CLEAN_RUN = [_assistant("done"), _result(result="done")]


def _role_log(
    main: Path,
    stamp: str,
    events: list[dict],
    *,
    age_seconds: float,
    now: datetime,
    backend_line: str | None = "claude",
    role: str = ROLE,
) -> Path:
    directory = _cache(main) / role
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{stamp}.log"
    path.write_text("\n".join(_header(backend_line) + [json.dumps(e) for e in events]) + "\n")
    mtime = now.timestamp() - age_seconds
    os.utime(path, (mtime, mtime))
    return path


def _verdict(main: Path, now: datetime, backend: str = ROLE_BACKEND):
    return read_persisted_quota_verdict(backend, cache_dir=_cache(main), now=now)


def _verdict_file(main: Path, backend: str = ROLE_BACKEND) -> Path:
    return _cache(main) / f"agent_guard_{backend}.json"


# ---- (a) a rejection on a role's own run --------------------------------------------------------


def test_a_role_run_rejected_on_quota_makes_the_verdict_exhausted_inside_the_ttl(tmp_path):
    now = datetime.now(UTC)
    _role_log(tmp_path, "20260918T084846Z", REJECTED_RUN, age_seconds=300, now=now)

    lines = agent_guard.fold_role_quota_observations(main=tmp_path, now=now)

    verdict = _verdict(tmp_path, now)
    assert verdict.status == "exhausted"
    # Aged from the rejection itself, not from the fold that wrote it.
    assert verdict.age_seconds == pytest.approx(300, abs=2)
    assert lines == [f"{ROLE_BACKEND}: quota verdict exhausted from role log 20260918T084846Z.log"]


def test_the_next_launch_of_a_role_with_a_fallback_takes_it(tmp_path):
    now = datetime.now(UTC)
    _role_log(tmp_path, "20260918T084846Z", REJECTED_RUN, age_seconds=60, now=now)
    agent_guard.fold_role_quota_observations(main=tmp_path, now=now)

    _, plan, verdict = role_launch(ROLE, cache_dir=_cache(tmp_path), now=now)

    task_class = load_role_class(ROLE)[1]
    assert task_class.fallback is not None, "the test needs a role class that declares a fallback"
    assert verdict.status == "exhausted"
    assert plan.substituted is True
    assert plan.backend == task_class.fallback.backend


def test_a_rejection_carried_only_by_the_result_is_also_exhausted(tmp_path):
    now = datetime.now(UTC)
    events = [_assistant("", tokens=0), _result(is_error=True, api_error_status=429)]
    _role_log(tmp_path, "20260918T090000Z", events, age_seconds=60, now=now)
    agent_guard.fold_role_quota_observations(main=tmp_path, now=now)
    assert _verdict(tmp_path, now).status == "exhausted"


def test_the_backend_is_the_one_the_log_header_says_ran(tmp_path):
    now = datetime.now(UTC)
    _role_log(
        tmp_path,
        "20260918T090000Z",
        REJECTED_RUN,
        age_seconds=60,
        now=now,
        backend_line="qwen (FALLBACK for claude -- the guard's verdict reads exhausted)",
    )
    observations = agent_guard.role_log_quota_observations(main=tmp_path, now=now)
    assert set(observations) == {"qwen"}


def test_a_log_written_before_the_header_named_a_backend_counts_for_the_classs_own(tmp_path):
    now = datetime.now(UTC)
    _role_log(
        tmp_path, "20260918T084846Z", REJECTED_RUN, age_seconds=60, now=now, backend_line=None
    )
    observations = agent_guard.role_log_quota_observations(main=tmp_path, now=now)
    assert set(observations) == {ROLE_BACKEND}


# ---- (b) the agent's own words are never the verdict --------------------------------------------


def test_a_run_whose_agent_claims_exhaustion_but_the_backend_served_is_not_exhausted(tmp_path):
    now = datetime.now(UTC)
    claim = "My quota is exhausted, the rate limit rejected me, resets 12:30pm."
    events = [_assistant(claim), _result(result=claim)]
    _role_log(tmp_path, "20260918T090000Z", events, age_seconds=60, now=now)

    agent_guard.fold_role_quota_observations(main=tmp_path, now=now)

    assert _verdict(tmp_path, now).status == "allowed"


def test_a_claim_in_a_run_that_never_reached_its_result_writes_nothing(tmp_path):
    now = datetime.now(UTC)
    events = [_assistant("I have hit my session limit, you've hit your session limit")]
    _role_log(tmp_path, "20260918T090000Z", events, age_seconds=60, now=now)

    assert agent_guard.fold_role_quota_observations(main=tmp_path, now=now) == []
    assert not _verdict_file(tmp_path).exists()
    assert _verdict(tmp_path, now).status == "unknown"


# ---- (c) a failure that is not a quota wall leaves the verdict as it was ------------------------


@pytest.mark.parametrize(
    "events",
    [
        pytest.param(
            [_result(is_error=True, num_turns=0, result="[API Error: Connection reset]")],
            id="transport-error",
        ),
        pytest.param([_assistant("half a turn")], id="crash-without-result"),
        pytest.param([], id="empty-log"),
    ],
)
def test_a_non_quota_termination_leaves_the_verdict_unchanged(tmp_path, events):
    now = datetime.now(UTC)
    verdict_file = _verdict_file(tmp_path)
    verdict_file.parent.mkdir(parents=True)
    verdict_file.write_text(json.dumps({"last_quota_status": "exhausted"}))
    before = now.timestamp() - 600
    os.utime(verdict_file, (before, before))
    before_ns = verdict_file.stat().st_mtime_ns

    _role_log(tmp_path, "20260918T090000Z", events, age_seconds=60, now=now)
    assert agent_guard.fold_role_quota_observations(main=tmp_path, now=now) == []

    assert json.loads(verdict_file.read_text()) == {"last_quota_status": "exhausted"}
    assert verdict_file.stat().st_mtime_ns == before_ns


@pytest.mark.parametrize(
    "events",
    [
        pytest.param([_result(is_error=True, num_turns=0)], id="transport-error"),
        pytest.param([_assistant("half a turn")], id="crash-without-result"),
        pytest.param([], id="empty-log"),
    ],
)
def test_a_non_quota_termination_says_nothing_about_the_quota(tmp_path, events):
    now = datetime.now(UTC)
    path = _role_log(tmp_path, "20260918T090000Z", events, age_seconds=60, now=now)
    assert agent_guard.role_run_quota_status(path) is None


# ---- (d) the TTL applies exactly as it does to a worker's verdict -------------------------------


def test_a_rejection_older_than_the_ttl_reads_unknown(tmp_path):
    now = datetime.now(UTC)
    _role_log(tmp_path, "20260918T084846Z", REJECTED_RUN, age_seconds=TTL_SECONDS + 60, now=now)

    assert agent_guard.fold_role_quota_observations(main=tmp_path, now=now) == []

    assert _verdict(tmp_path, now).status == "unknown"
    _, plan, _ = role_launch(ROLE, cache_dir=_cache(tmp_path), now=now)
    assert plan.substituted is False


def test_a_folded_rejection_ages_past_the_ttl_like_a_workers(tmp_path):
    written_at = datetime.now(UTC)
    _role_log(tmp_path, "20260918T084846Z", REJECTED_RUN, age_seconds=60, now=written_at)
    agent_guard.fold_role_quota_observations(main=tmp_path, now=written_at)

    later = datetime.fromtimestamp(written_at.timestamp() + TTL_SECONDS, UTC)
    _, plan, verdict = role_launch(ROLE, cache_dir=_cache(tmp_path), now=later)
    assert verdict.status == "exhausted"
    assert verdict.age_seconds > TTL_SECONDS
    assert plan.substituted is False
    assert plan.backend == ROLE_BACKEND


# ---- (e) idempotence: the same rejection seen twice does not refresh the verdict ---------------


def test_the_same_rejection_seen_in_two_ticks_does_not_move_the_verdicts_time(tmp_path):
    first_tick = datetime.now(UTC)
    _role_log(tmp_path, "20260918T084846Z", REJECTED_RUN, age_seconds=120, now=first_tick)
    agent_guard.fold_role_quota_observations(main=tmp_path, now=first_tick)
    after_first = _verdict_file(tmp_path).stat().st_mtime_ns

    second_tick = datetime.fromtimestamp(first_tick.timestamp() + 300, UTC)
    assert agent_guard.fold_role_quota_observations(main=tmp_path, now=second_tick) == []
    assert _verdict_file(tmp_path).stat().st_mtime_ns == after_first


def test_a_newer_rejection_does_refresh_it(tmp_path):
    now = datetime.now(UTC)
    _role_log(tmp_path, "20260918T084846Z", REJECTED_RUN, age_seconds=600, now=now)
    agent_guard.fold_role_quota_observations(main=tmp_path, now=now)
    newer = _role_log(tmp_path, "20260918T085500Z", REJECTED_RUN, age_seconds=30, now=now)

    agent_guard.fold_role_quota_observations(main=tmp_path, now=now)

    assert _verdict_file(tmp_path).stat().st_mtime_ns == newer.stat().st_mtime_ns


# ---- merging with what the file already holds --------------------------------------------------


def test_the_most_recent_role_observation_wins(tmp_path):
    now = datetime.now(UTC)
    _role_log(tmp_path, "20260918T084846Z", REJECTED_RUN, age_seconds=600, now=now)
    _role_log(tmp_path, "20260918T090000Z", CLEAN_RUN, age_seconds=60, now=now)
    agent_guard.fold_role_quota_observations(main=tmp_path, now=now)
    assert _verdict(tmp_path, now).status == "allowed"


def test_a_worker_observation_newer_than_the_role_log_is_kept(tmp_path):
    now = datetime.now(UTC)
    verdict_file = _verdict_file(tmp_path)
    verdict_file.parent.mkdir(parents=True)
    verdict_file.write_text(json.dumps({"commit_count": 3, "last_quota_status": "allowed"}))
    _role_log(tmp_path, "20260918T084846Z", REJECTED_RUN, age_seconds=600, now=now)

    assert agent_guard.fold_role_quota_observations(main=tmp_path, now=now) == []
    assert _verdict(tmp_path, now).status == "allowed"


def test_the_fold_carries_the_stall_bookkeeping_over(tmp_path):
    now = datetime.now(UTC)
    verdict_file = _verdict_file(tmp_path)
    verdict_file.parent.mkdir(parents=True)
    verdict_file.write_text(
        json.dumps({"commit_count": 3, "turn_count_at_commit": 7, "last_quota_status": "allowed"})
    )
    old = now.timestamp() - 900
    os.utime(verdict_file, (old, old))
    _role_log(tmp_path, "20260918T084846Z", REJECTED_RUN, age_seconds=60, now=now)

    agent_guard.fold_role_quota_observations(main=tmp_path, now=now)

    recorded = json.loads(verdict_file.read_text())
    assert recorded["commit_count"] == 3
    assert recorded["turn_count_at_commit"] == 7
    assert recorded["last_quota_status"] == "exhausted"


def test_a_busy_verdict_file_is_left_for_the_next_fold_rather_than_waited_on(tmp_path):
    import fcntl

    now = datetime.now(UTC)
    _role_log(tmp_path, "20260918T084846Z", REJECTED_RUN, age_seconds=60, now=now)
    lock_path = _verdict_file(tmp_path).with_name(_verdict_file(tmp_path).name + ".lock")
    with lock_path.open("a") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lines = agent_guard.fold_role_quota_observations(main=tmp_path, now=now)
    assert lines == [f"{ROLE_BACKEND}: verdict file busy -- role observation left for next fold"]
    assert not _verdict_file(tmp_path).exists()


# ---- the two entry points fold before they can launch anything ---------------------------------


def test_wake_folds_the_rejection_before_it_invokes_the_planner(tmp_path, monkeypatch):
    now = datetime.now(UTC)
    _role_log(tmp_path, "20260918T084846Z", REJECTED_RUN, age_seconds=30, now=now, role="validator")
    agent_guard.write_event("validator_finished", "399", main=tmp_path, now=now)
    seen_at_launch: list[str] = []

    def invoke_planner(context, *, main):
        seen_at_launch.append(_verdict(main, now).status)

    monkeypatch.setattr(agent_guard, "_invoke_planner", invoke_planner)
    agent_guard.wake(main=tmp_path, now=now)

    assert seen_at_launch == ["exhausted"]


def test_tick_folds_before_it_checks_any_worker(tmp_path, monkeypatch):
    now = datetime.now(UTC)
    _role_log(tmp_path, "20260918T084846Z", REJECTED_RUN, age_seconds=30, now=now)
    seen_by_worker_check: list[str] = []

    def tick_backend(backend, *, main, now=None):
        seen_by_worker_check.append(_verdict(main, datetime.now(UTC)).status)
        return agent_guard.TickResult(backend, f"{backend}: never started")

    monkeypatch.setattr(agent_guard, "_tick_backend", tick_backend)
    monkeypatch.setattr(agent_guard, "_agents_paused", lambda *, main: True)
    agent_guard.tick(main=tmp_path, now=now)

    assert seen_by_worker_check and set(seen_by_worker_check) == {"exhausted"}


def test_a_role_observation_never_writes_quota_changed(tmp_path, monkeypatch):
    now = datetime.now(UTC)
    _role_log(tmp_path, "20260918T084846Z", REJECTED_RUN, age_seconds=30, now=now)
    monkeypatch.setattr(agent_guard, "_invoke_planner", lambda context, *, main: None)
    agent_guard.wake(main=tmp_path, now=now)
    assert not [p for p in agent_guard.pending_events(tmp_path) if "quota_changed" in p.name]
