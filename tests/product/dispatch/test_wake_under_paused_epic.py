"""`wake` and `check` honour `status:agents-paused`: events stay on disk and no planner runs."""

from __future__ import annotations

import os
import pathlib
import shlex

import pytest
from test_agent_guard import _fake_completed

from agent_os import guard as agent_guard


@pytest.fixture
def invocations(monkeypatch) -> list[str]:
    calls: list[str] = []
    monkeypatch.setattr(
        agent_guard, "_invoke_planner", lambda context, *, main: calls.append(context)
    )
    return calls


def test_wake_does_not_invoke_the_planner_while_the_epic_is_paused(
    tmp_path, monkeypatch, invocations
):
    monkeypatch.setattr(agent_guard, "_agents_paused", lambda *, main: True)
    agent_guard.write_event("worker_finished", "claude", detail="done", main=tmp_path)
    message = agent_guard.wake(main=tmp_path)
    assert agent_guard.AGENTS_PAUSED_LABEL in message
    assert invocations == []
    assert len(agent_guard.pending_events(tmp_path)) == 1


def test_check_by_hand_under_a_paused_epic_records_the_event_but_wakes_no_planner(
    tmp_path, monkeypatch, invocations
):
    monkeypatch.setattr(agent_guard, "_agents_paused", lambda *, main: True)
    agent_guard.cache_dir(tmp_path).mkdir(parents=True)
    agent_guard.check("claude", main=tmp_path)
    assert invocations == []
    assert len(agent_guard.pending_events(tmp_path)) == 1


def test_wake_runs_the_planner_once_the_pause_is_lifted(tmp_path, monkeypatch, invocations):
    paused = {"now": True}
    monkeypatch.setattr(agent_guard, "_agents_paused", lambda *, main: paused["now"])
    agent_guard.write_event("worker_finished", "claude", detail="done", main=tmp_path)
    agent_guard.wake(main=tmp_path)
    paused["now"] = False
    agent_guard.wake(main=tmp_path)
    assert invocations == ["done"]


@pytest.fixture
def real_gh_trap(tmp_path, monkeypatch) -> pathlib.Path:
    """A `gh` first in `PATH` that records being called: reaching it means a test asked GitHub."""
    trap_dir = tmp_path / "trap-bin"
    trap_dir.mkdir()
    marker = tmp_path / "GH-WAS-CALLED"
    trap = trap_dir / "gh"
    trap.write_text(f'#!/bin/sh\necho "$@" >> {shlex.quote(str(marker))}\nexit 1\n')
    trap.chmod(0o755)
    monkeypatch.setenv("PATH", f"{trap_dir}:{os.environ['PATH']}")
    return marker


def test_wake_does_not_ask_github_whether_the_epic_is_paused_unless_a_test_says_so(
    tmp_path, invocations, real_gh_trap
):
    """`wake` reads the epic's labels with a real `gh issue view`; a test that does not care about
    the pause must not reach GitHub for it, and so the suite's default is 'not paused'."""
    agent_guard.write_event("worker_finished", "claude", detail="done", main=tmp_path)
    agent_guard.wake(main=tmp_path)
    assert not real_gh_trap.exists(), real_gh_trap.read_text()
    assert invocations == ["done"]


def test_check_does_not_ask_github_whether_the_epic_is_paused_unless_a_test_says_so(
    tmp_path, invocations, real_gh_trap
):
    agent_guard.cache_dir(tmp_path).mkdir(parents=True)
    agent_guard.check("claude", main=tmp_path)
    assert not real_gh_trap.exists(), real_gh_trap.read_text()


@pytest.mark.real_agents_paused
def test_agents_paused_true_when_the_epic_carries_the_label(monkeypatch, tmp_path):
    monkeypatch.setattr(
        agent_guard.subprocess,
        "run",
        lambda cmd, **kwargs: _fake_completed(
            cmd, {"labels": [{"name": agent_guard.AGENTS_PAUSED_LABEL}]}
        ),
    )
    assert agent_guard._agents_paused(main=tmp_path) is True


@pytest.mark.real_agents_paused
def test_agents_paused_false_when_the_epic_does_not_carry_the_label(monkeypatch, tmp_path):
    monkeypatch.setattr(
        agent_guard.subprocess,
        "run",
        lambda cmd, **kwargs: _fake_completed(cmd, {"labels": [{"name": "type:epic"}]}),
    )
    assert agent_guard._agents_paused(main=tmp_path) is False
