"""Which slot the driver makes when every one is busy, and when it makes none."""

from __future__ import annotations

import pytest

from agent_os.lib import ProjectConfig
from agent_os.product.dispatch.slots.creation import SlotRefusal, plan_new_slot


def project(*, other_backend="other", other_worktree="../host-other"):
    return ProjectConfig(
        repo="owner/name",
        tracking_epic=1,
        board_number=1,
        backends={
            "claude": {"worktree": "../host-claude", "stream": "claude_jsonl"},
            other_backend: {"worktree": other_worktree, "stream": "claude_jsonl"},
        },
    )


def plan(tmp_path, configured=None, *, alive=1, cap=None, exhausted=False):
    host = tmp_path / "host"
    host.mkdir(exist_ok=True)
    return plan_new_slot(
        configured or project(),
        "claude",
        root=host,
        alive_workers=alive,
        cap=cap,
        quota_exhausted=exhausted,
    )


def test_the_next_slot_follows_the_highest_one_the_backend_has(tmp_path):
    (tmp_path / "host-claude-2" / ".git").mkdir(parents=True)
    (tmp_path / "host-claude-4" / ".git").mkdir(parents=True)
    new_slot = plan(tmp_path)
    assert (new_slot.number, new_slot.key) == (5, "claude-5")
    assert new_slot.worktree == (tmp_path / "host-claude-5").resolve()
    assert new_slot.as_driver_line() == f"claude\t5\tclaude-5\t{new_slot.worktree}"


def test_without_a_cap_the_number_of_workers_alive_is_no_reason_to_refuse(tmp_path):
    assert plan(tmp_path, alive=40, cap=None).number == 2


def test_a_cap_the_host_set_is_the_reason_when_it_is_reached(tmp_path):
    with pytest.raises(SlotRefusal, match=r"3 worker\(s\) already running.*max_parallel_issues=3"):
        plan(tmp_path, alive=3, cap=3)
    assert plan(tmp_path, alive=2, cap=3).number == 2


def test_an_exhausted_quota_is_a_reason_even_below_the_cap(tmp_path):
    with pytest.raises(SlotRefusal, match="quota exhausted"):
        plan(tmp_path, alive=1, cap=9, exhausted=True)


def test_a_backend_named_like_the_next_slot_is_a_collision_that_is_refused_loudly(tmp_path):
    with pytest.raises(SlotRefusal, match=r"worker_claude-2\.\* belong to backend 'claude-2'"):
        plan(tmp_path, project(other_backend="claude-2"))


def test_a_worktree_that_is_another_backends_is_never_made_over(tmp_path):
    with pytest.raises(SlotRefusal, match="already the worktree of backend 'other'"):
        plan(tmp_path, project(other_worktree="../host-claude-2"))
