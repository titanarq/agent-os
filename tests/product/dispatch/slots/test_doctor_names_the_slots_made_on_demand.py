"""The doctor's `worktrees exist` check reads the slots the driver made, not only the configured."""

from __future__ import annotations

from agent_os import doctor
from agent_os.lib import ProjectConfig


def test_the_slots_found_on_disk_are_named_with_the_precreated_ones(tmp_path):
    host = tmp_path / "host"
    host.mkdir()
    for directory in ("host-claude", "host-claude-2", "host-claude-3"):
        (tmp_path / directory / ".git").mkdir(parents=True)
    project = ProjectConfig(
        repo="owner/name",
        tracking_epic=1,
        board_number=1,
        backends={"claude": {"worktree": "../host-claude", "stream": "claude_jsonl"}},
    )

    check = doctor.check_worktrees(project, host)

    assert check.ok and "claude-2" in check.detail and "claude-3" in check.detail
