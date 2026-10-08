"""`wake` and `check` honour `status:agents-paused`: events stay on disk and no planner runs."""

from __future__ import annotations

import pytest

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
