"""`open-pr` whose merge never starts ends as visibly as its other refusals.

On the first v2 host a run ended `BLOCKED reason=merge_failed` and its issue stayed `status:doing`
with no comment: the planner's prompt says to make such an issue `blocked-on-human`, but the three
other endings of `open-pr` do it in the driver, and a ticket the driver leaves mute reaches the
owner only if the planner happens to act. Owner's rule
(`fr-the-owner-is-asked-only-in-sessions-they-open`): what is blocked is shown to them in their
session, never silent.

The harness is `test_worker_task.py`'s own: a worktree with a real local origin and a stub `gh`.
"""

from __future__ import annotations

import subprocess

from test_worker_task import _advance_the_base, _open_pr, worker_at_its_end  # noqa: F401

BLOCKED_STATE = "BLOCKED reason=merge_failed base=main"


def head_of(worktree):
    return subprocess.run(
        ["git", "-C", str(worktree), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def make_an_untracked_file_block_the_merge(worktree, remote):
    _advance_the_base(
        remote, path="NEW.md", contents="from the base\n", subject="the base added it"
    )
    (worktree / "NEW.md").write_text("untracked, and in the way\n")


def test_a_merge_that_never_starts_moves_the_issue_to_blocked_on_human(worker_at_its_end):  # noqa: F811
    environment, worktree, remote, cache, calls = worker_at_its_end
    make_an_untracked_file_block_the_merge(worktree, remote)

    result = _open_pr(environment)

    assert result.returncode == 1, result.stdout + result.stderr
    assert (cache / "worker_claude.state").read_text().splitlines()[:2] == [
        BLOCKED_STATE,
        "issue=348 label=status:blocked-on-human",
    ]
    recorded = calls.read_text()
    assert "labels[]=status:blocked-on-human" in recorded, recorded
    assert "labels[]=status:ai-completed" not in recorded, recorded
    assert "pr\tcreate" not in recorded, recorded


def test_the_comment_says_what_was_in_the_way_and_how_to_unblock_it(worker_at_its_end):  # noqa: F811
    environment, worktree, remote, _cache, calls = worker_at_its_end
    make_an_untracked_file_block_the_merge(worktree, remote)

    _open_pr(environment)

    recorded = calls.read_text()
    posted = [line for line in recorded.splitlines() if "/comments\t-X\tPOST" in line]
    assert len(posted) == 1, recorded
    assert "merging `main` into it never started" in recorded
    assert "?? NEW.md" in recorded
    assert "worker_task.sh claude open-pr" in recorded


def test_the_branch_is_left_unpushed_and_as_the_worker_wrote_it(worker_at_its_end):  # noqa: F811
    environment, worktree, remote, _cache, _calls = worker_at_its_end
    make_an_untracked_file_block_the_merge(worktree, remote)
    head_before = head_of(worktree)

    _open_pr(environment)

    assert head_of(worktree) == head_before
    remote_has_the_branch = subprocess.run(
        ["git", "-C", str(remote), "rev-parse", "--verify", "claude/348-pr"],
        capture_output=True,
        check=False,
    )
    assert remote_has_the_branch.returncode != 0
