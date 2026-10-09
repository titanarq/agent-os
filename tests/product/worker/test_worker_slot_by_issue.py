"""`collect`, `open-pr`, `stop` and `watch` take `--issue <N>` to find their slot (stage1i, #4).

On a backend with `slots: 2+` they refused with a usage error unless `--slot` was given, though
the slot is knowable: it is the one that recorded the issue, which is how `resume --issue` already
finds it (#90). The planner and a human both hold an issue number, never a slot number.
"""

from __future__ import annotations

import pytest
from test_worker_slots import (
    _cache_files,
    _driver,
    _pid_alive,
    _slotted_environment,
    _stop_every_slot,
)

TWO_ISSUES = {"347": ["module:workers"], "348": ["module:prices"]}


def _two_runs(tmp_path):
    environment, cache, worktrees = _slotted_environment(tmp_path, labels_by_issue=TWO_ISSUES)
    assert _driver(environment, "start", "347").returncode == 0
    assert _driver(environment, "start", "348").returncode == 0
    assert (cache / "worker_claude.issue").read_text().strip() == "347"
    assert (cache / "worker_claude-2.issue").read_text().strip() == "348"
    return environment, cache, worktrees


def test_stop_by_issue_stops_only_the_slot_that_recorded_it(tmp_path):
    environment, cache, _worktrees = _two_runs(tmp_path)
    try:
        result = _driver(environment, "stop", "--issue", "348")
        assert result.returncode == 0, result.stdout + result.stderr
        assert not _pid_alive(cache / "worker_claude-2.pid")
        assert _pid_alive(cache / "worker_claude.pid"), "the other slot's run was stopped too"
    finally:
        _stop_every_slot(environment, 2)


def test_collect_by_issue_reports_the_worktree_of_that_slot(tmp_path):
    environment, _cache, _worktrees = _two_runs(tmp_path)
    try:
        result = _driver(environment, "collect", "--issue", "348")
        assert result.returncode == 0, result.stdout + result.stderr
        assert "=== commits ===" in result.stdout
        assert "the run is still alive" in result.stdout
    finally:
        _stop_every_slot(environment, 2)


def test_open_pr_by_issue_addresses_the_slot_that_recorded_it(tmp_path):
    environment, cache, _worktrees = _slotted_environment(tmp_path, labels_by_issue={})
    (cache / "worker_claude-2.issue").write_text("348\n")
    (cache / "worker_claude-2.state").write_text("CUT_BY_GUARD reason=stall\n")
    result = _driver(environment, "open-pr", "--issue", "348")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "CUT_BY_GUARD reason=stall -- no pull request" in result.stdout


@pytest.mark.parametrize("subcommand", ["collect", "open-pr", "stop", "watch"])
def test_an_issue_no_slot_recorded_is_refused_and_writes_nothing(tmp_path, subcommand):
    environment, cache, _worktrees = _slotted_environment(tmp_path, labels_by_issue={})
    (cache / "worker_claude-2.issue").write_text("348\n")
    before = _cache_files(cache)
    result = _driver(environment, subcommand, "--issue", "999")
    assert result.returncode == 1, result.stdout + result.stderr
    assert f"{subcommand} refused: no slot of backend 'claude' recorded issue #999" in result.stdout
    assert _cache_files(cache) == before


@pytest.mark.parametrize("subcommand", ["collect", "open-pr", "stop", "watch"])
def test_without_a_slot_or_an_issue_the_refusal_names_both_ways_in(tmp_path, subcommand):
    environment, _cache, _worktrees = _slotted_environment(tmp_path, labels_by_issue={})
    result = _driver(environment, subcommand)
    assert result.returncode == 2
    assert "--slot" in result.stdout and "--issue" in result.stdout


def test_an_explicit_slot_that_recorded_another_issue_is_refused(tmp_path):
    environment, cache, _worktrees = _slotted_environment(tmp_path, labels_by_issue={})
    (cache / "worker_claude-2.issue").write_text("348\n")
    result = _driver(environment, "stop", "--slot", "1", "--issue", "348")
    assert result.returncode == 1
    assert (
        "stop refused: slot 1 of backend 'claude' recorded issue #none, not #348" in result.stdout
    )
