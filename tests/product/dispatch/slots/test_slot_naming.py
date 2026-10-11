"""Which slots a host has: the ones its config precreates and the ones the driver made on demand."""

from __future__ import annotations

from agent_os.lib import ProjectConfig
from agent_os.product.dispatch.slots.naming import (
    slot_numbers_made_on_demand,
    worker_slot_key,
    worker_slots,
)


def project(root, **backend_options):
    return ProjectConfig(
        repo="owner/name",
        tracking_epic=1,
        board_number=1,
        backends={
            "claude": {"worktree": "../host-claude", "stream": "claude_jsonl", **backend_options},
            "other": {"worktree": "../elsewhere", "stream": "claude_jsonl"},
        },
    )


def worktree(path):
    (path / ".git").mkdir(parents=True)


def test_the_config_alone_gives_the_precreated_slots(tmp_path):
    host = tmp_path / "host"
    host.mkdir()
    assert worker_slots(project(host, slots=2)) == [("claude", 1), ("claude", 2), ("other", 1)]


def test_the_slots_the_driver_made_are_found_where_it_puts_them(tmp_path):
    host = tmp_path / "host"
    host.mkdir()
    worktree(tmp_path / "host-claude-3")
    worktree(tmp_path / "host-claude-5")
    assert slot_numbers_made_on_demand(project(host), "claude", host) == [3, 5]
    assert worker_slots(project(host), host) == [
        ("claude", 1),
        ("claude", 3),
        ("claude", 5),
        ("other", 1),
    ]


def test_a_directory_without_a_worktree_in_it_is_not_a_slot(tmp_path):
    host = tmp_path / "host"
    host.mkdir()
    (tmp_path / "host-claude-3").mkdir()
    (tmp_path / "host-claude-backup").mkdir()
    assert slot_numbers_made_on_demand(project(host), "claude", host) == []


def test_a_slot_the_config_already_precreates_is_not_counted_twice(tmp_path):
    host = tmp_path / "host"
    host.mkdir()
    worktree(tmp_path / "host-claude-2")
    worktree(tmp_path / "host-claude-3")
    assert slot_numbers_made_on_demand(project(host, slots=2), "claude", host) == [3]


def test_another_backends_own_worktree_is_never_taken_for_a_slot(tmp_path):
    host = tmp_path / "host"
    host.mkdir()
    configured = ProjectConfig(
        repo="owner/name",
        tracking_epic=1,
        board_number=1,
        backends={
            "claude": {"worktree": "../host-claude", "stream": "claude_jsonl"},
            "other": {"worktree": "../host-claude-2", "stream": "claude_jsonl"},
        },
    )
    worktree(tmp_path / "host-claude-2")
    assert slot_numbers_made_on_demand(configured, "claude", host) == []


def test_a_slot_is_keyed_by_the_backend_for_the_first_and_by_its_number_after():
    assert worker_slot_key("claude", 1) == "claude"
    assert worker_slot_key("claude", 4) == "claude-4"
