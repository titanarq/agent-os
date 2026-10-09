"""`open-pr` runs the code-quality ratchet on the worker's branch before it opens the pull request.

Two tickets of the first v2 host came back `CHANGES_REQUESTED` only because a file they touched
passed the line limit, and every such round costs a full worker run. The host's CI runs
`agent-os-quality` on the pull request afterwards; the driver now asks the same question of the
same worktree first and refuses to announce a branch that would be red from its first minute.

The harness is `test_worker_task.py`'s own: a worktree with a real local origin, a stub `gh`, and no
backend anywhere.
"""

from __future__ import annotations

import subprocess

from test_worker_task import _git, _open_pr, worker_at_its_end  # noqa: F401

from agent_os.cli import AGENT_OS_DIR

BLOCKED_STATE = "BLOCKED reason=quality_ratchet_failed branch=claude/348-pr"
LINES_OVER_THE_LIMIT = 301


def commit_a_file_of(worktree, name, line_count):
    (worktree / name).write_text("x = 1\n" * line_count)
    _git("add", name, cwd=worktree)
    _git("commit", "-qm", f"stage 1/1: write {name}", cwd=worktree)


def was_pushed(remote):
    return (
        subprocess.run(
            ["git", "-C", str(remote), "rev-parse", "--verify", "claude/348-pr"],
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


def test_open_pr_refuses_a_new_file_over_the_line_limit(worker_at_its_end):  # noqa: F811
    """The driver runs from the host's main checkout, which is clean: a ratchet that measured it
    instead of the worktree (`--root` left out) would report this branch as sound."""
    environment, worktree, remote, cache, calls = worker_at_its_end
    commit_a_file_of(worktree, "readme_that_grew.md", LINES_OVER_THE_LIMIT)

    result = _open_pr(environment)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "readme_that_grew.md: new, 301 lines (limit 300)" in result.stdout, result.stdout
    assert (cache / "worker_claude.state").read_text().splitlines()[:2] == [
        BLOCKED_STATE,
        "issue=348 label=status:blocked-on-human",
    ]
    recorded = calls.read_text()
    assert "pr\tcreate" not in recorded, recorded
    assert "labels[]=status:ai-completed" not in recorded, recorded
    assert "labels[]=status:blocked-on-human" in recorded, recorded
    posted = [line for line in recorded.splitlines() if "/comments\t-X\tPOST" in line]
    assert len(posted) == 1, recorded
    assert "readme_that_grew.md: new, 301 lines (limit 300)" in recorded
    assert "agent_os.quality --base origin/main" in recorded
    assert not was_pushed(remote), "a branch that fails the ratchet was pushed"


def test_open_pr_leaves_the_branch_as_the_worker_wrote_it(worker_at_its_end):  # noqa: F811
    """Refused, not repaired: splitting a file is the worker's job, and this step edits nothing."""
    environment, worktree, _remote, _cache, _calls = worker_at_its_end
    commit_a_file_of(worktree, "readme_that_grew.md", LINES_OVER_THE_LIMIT)
    head_before = _head_of(worktree)

    _open_pr(environment)

    assert _head_of(worktree) == head_before


def test_open_pr_opens_the_pull_request_for_a_file_within_the_limit(worker_at_its_end):  # noqa: F811
    environment, worktree, _remote, cache, calls = worker_at_its_end
    commit_a_file_of(worktree, "readme_within_limit.md", LINES_OVER_THE_LIMIT - 1)

    result = _open_pr(environment)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "pr\tcreate" in calls.read_text()
    assert (cache / "worker_claude.state").read_text().splitlines()[0] == "STARTED"


def test_open_pr_does_not_refuse_over_a_ratchet_that_could_not_run(worker_at_its_end):  # noqa: F811
    """No merge-base with the base is `agent-os-quality` exit 2, "could not run" -- a failure of
    the tool and not a verdict on the branch, and the host's CI will judge the pull request."""
    environment, worktree, _remote, cache, _calls = worker_at_its_end
    _git("checkout", "-q", "--orphan", "claude/348-pr-orphan", cwd=worktree)
    _git("commit", "-qm", "stage 1/1: an unrelated history", cwd=worktree)
    _git("branch", "-q", "-M", "claude/348-pr", cwd=worktree)

    result = _open_pr(environment)

    assert "the quality ratchet could not run" in result.stdout, result.stdout
    assert BLOCKED_STATE not in (cache / "worker_claude.state").read_text()


def test_the_worker_prompt_tells_it_to_run_the_ratchet_on_its_own_worktree_before_a_stage_ends():
    prompt = " ".join((AGENT_OS_DIR / "prompts" / "worker.md").read_text().split())
    assert '"$AGENT_OS_PYTHON" -m agent_os.quality --base origin/main`' in prompt
    assert "run it in your worktree and never in the main checkout" in prompt
    assert "Before the commit that closes a stage" in prompt


def _head_of(worktree):
    return subprocess.run(
        ["git", "-C", str(worktree), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
