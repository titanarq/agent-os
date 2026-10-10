"""A dispatch that finds every slot busy makes the next one (stage 1l).

`slots:` used to be a ceiling: with the one slot busy `branch` said "a run is alive" and a backend
with every slot busy said "every slot of backend 'claude' is busy", so a host had to guess how many
workers it would need. The owner (2026-10-09): "no se deben limitar" -- quota is the only limit
(docs/tree/fr-independent-work-runs-in-parallel.md). Now the driver makes the next slot, reuses an
idle one first, and stops only for what the tree names: the cap a host chose to set, and a backend
whose quota reads exhausted.

Real `worker_task.sh`, stub `gh`, a fake `claude` that never exits, and a throwaway host root with a
bare origin (the new worktree is made from the host root): no real backend, no real repository.
"""

from __future__ import annotations

import json
import os
import re
import time
from types import SimpleNamespace

from test_worker_slots import (
    _cache_files,
    _driver,
    _pid_alive,
    _slotted_environment,
    _stop_every_slot,
)

LABELS = {"347": ["module:workers"], "348": ["module:prices"], "349": ["module:reports"]}


def _environment(tmp_path, *, cap=None):
    """One slot configured (`slots: 1`, nothing precreated beyond it) and, unless `cap` says
    otherwise, no `planner.max_parallel_issues` at all -- the new default."""
    environment, cache, worktrees = _slotted_environment(
        tmp_path, slots=1, max_parallel_issues=cap or 1, labels_by_issue=LABELS
    )
    if cap is None:
        config = tmp_path / "agents-slots.yaml"
        config.write_text(re.sub(r"\n *max_parallel_issues:[^\n]*", "", config.read_text()))
    return environment, cache, worktrees[0]


def _dispatch(environment, issue, slug):
    """What the planner does for one issue -- `branch`, then `start` -- as one result whose output
    is both commands' (the slot is made by `branch`, which comes first)."""
    branched = _driver(environment, "branch", f"task/{issue}-{slug}", "main")
    started = branched if branched.returncode != 0 else _driver(environment, "start", issue)
    return SimpleNamespace(returncode=started.returncode, stdout=branched.stdout + started.stdout)


def test_a_dispatch_with_the_only_slot_busy_makes_a_second_slot_and_runs_in_it(tmp_path):
    environment, cache, _ = _environment(tmp_path)
    try:
        assert _dispatch(environment, "347", "one").returncode == 0
        second = _dispatch(environment, "348", "two")
        assert second.returncode == 0, second.stdout + second.stderr
        assert "slot 2 of backend 'claude' made on demand" in second.stdout
        assert "started pid" in second.stdout

        assert (cache / "worker_claude.issue").read_text().strip() == "347"
        assert (cache / "worker_claude-2.issue").read_text().strip() == "348"
        assert _pid_alive(cache / "worker_claude.pid") and _pid_alive(cache / "worker_claude-2.pid")
        assert (tmp_path / "wt-claude-2" / ".git").exists()
    finally:
        _stop_every_slot(environment, 2)


def test_every_slot_busy_is_no_reason_to_refuse_a_third(tmp_path):
    environment, cache, _ = _environment(tmp_path)
    try:
        for issue, slug in (("347", "one"), ("348", "two"), ("349", "three")):
            result = _dispatch(environment, issue, slug)
            assert result.returncode == 0, result.stdout + result.stderr
        assert (cache / "worker_claude-3.issue").read_text().strip() == "349"
        assert (tmp_path / "wt-claude-3" / ".git").exists()
    finally:
        _stop_every_slot(environment, 3)


def test_an_idle_slot_is_reused_before_another_is_made(tmp_path):
    environment, cache, _ = _environment(tmp_path)
    try:
        assert _dispatch(environment, "347", "one").returncode == 0
        assert _dispatch(environment, "348", "two").returncode == 0
        assert _driver(environment, "stop", "--issue", "348").returncode == 0

        third = _dispatch(environment, "349", "three")
        assert third.returncode == 0, third.stdout + third.stderr
        assert "made on demand" not in third.stdout
        assert (cache / "worker_claude-2.issue").read_text().strip() == "349"
        assert not (tmp_path / "wt-claude-3").exists()
    finally:
        _stop_every_slot(environment, 2)


def test_the_same_issue_is_never_started_twice_to_fill_a_new_slot(tmp_path):
    environment, cache, _ = _environment(tmp_path)
    try:
        assert _dispatch(environment, "347", "one").returncode == 0
        again = _driver(environment, "start", "347")
        assert again.returncode == 1
        assert "already alive" in again.stdout and "issue #347 in slot 1" in again.stdout
        assert not (tmp_path / "wt-claude-2").exists()
        assert not any(name.startswith("worker_claude-2.") for name in _cache_files(cache))
    finally:
        _stop_every_slot(environment, 1)


def test_a_cap_the_host_sets_refuses_before_a_slot_is_made(tmp_path):
    environment, cache, _ = _environment(tmp_path, cap=1)
    try:
        assert _dispatch(environment, "347", "one").returncode == 0
        before = _cache_files(cache)  # the lock file is the one thing a refusal may leave
        refused = _driver(environment, "branch", "task/348-two", "main")
        assert refused.returncode == 1
        assert "max_parallel_issues=1" in refused.stdout
        assert not (tmp_path / "wt-claude-2").exists()
        assert [name for name in _cache_files(cache) if name != "worker_slots.lock"] == before
    finally:
        _stop_every_slot(environment, 1)


def _quota_verdict(cache, status, *, age_seconds):
    verdict = cache / "agent_guard_claude.json"
    verdict.write_text(json.dumps({"last_quota_status": status}))
    observed = time.time() - age_seconds
    os.utime(verdict, (observed, observed))


def test_an_exhausted_quota_makes_no_slot(tmp_path):
    environment, cache, _ = _environment(tmp_path)
    try:
        assert _dispatch(environment, "347", "one").returncode == 0
        _quota_verdict(cache, "exhausted", age_seconds=30)
        refused = _driver(environment, "branch", "task/348-two", "main")
        assert refused.returncode == 1
        assert "quota exhausted" in refused.stdout
        assert not (tmp_path / "wt-claude-2").exists()
    finally:
        _stop_every_slot(environment, 1)


def test_an_exhausted_verdict_the_guard_has_not_refreshed_for_hours_blocks_nothing(tmp_path):
    environment, cache, _ = _environment(tmp_path)
    try:
        assert _dispatch(environment, "347", "one").returncode == 0
        _quota_verdict(cache, "exhausted", age_seconds=6 * 3600)
        assert _dispatch(environment, "348", "two").returncode == 0
        assert (tmp_path / "wt-claude-2" / ".git").exists()
    finally:
        _stop_every_slot(environment, 2)


def test_the_slots_the_driver_made_are_listed_where_the_guard_and_the_doctor_read_them(tmp_path):
    environment, _, _ = _environment(tmp_path)
    try:
        assert _dispatch(environment, "347", "one").returncode == 0
        assert _dispatch(environment, "348", "two").returncode == 0
        every_slot = _driver(environment, "status")
        assert "=== claude slot 1" in every_slot.stdout
        assert "=== claude slot 2" in every_slot.stdout
        assert "issue:     #348" in every_slot.stdout
    finally:
        _stop_every_slot(environment, 2)
