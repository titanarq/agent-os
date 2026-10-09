"""A stage whose commit is a merge counts as done (stage1i, from the vector host's #39).

The rework of #39 had one stage left, `git merge origin/main` with its conflicts resolved, and its
commit was a merge commit whose subject said `stage 2/2: ...`. The driver counts a branch's stages
off its first-parent commits and dropped merge commits from that list (`--no-merges`), so it counted
1/2, cut the run as `no_stage_commit` and `open-pr` refused to publish; the host fixed `.state` and
`.stage` by hand. What keeps another issue's stages out of the count is `--first-parent` -- the base
merged into the branch is a second parent -- and not `--no-merges`.
"""

from __future__ import annotations

import subprocess

from test_worker_task import DRIVER, ROOT, _git, _staged_environment

BRANCH = "claude/347-staged"


def _branch_with_a_merge(tmp_path, merge_subject, side_subject):
    environment, cache, worktree, _tmp = _staged_environment(
        tmp_path,
        stage_titles=("Write the failing test", "Make it pass"),
        mode="hang",
        subjects=("stage 1/2: Write the failing test",),
    )
    _git("checkout", "-q", "-b", "side", "main", cwd=worktree)
    (worktree / "side.txt").write_text("a change that came from the base\n")
    _git("add", "side.txt", cwd=worktree)
    _git("commit", "-qm", side_subject, cwd=worktree)
    _git("checkout", "-q", BRANCH, cwd=worktree)
    _git("merge", "--no-ff", "-q", "-m", merge_subject, "side", cwd=worktree)
    (cache / "worker_claude.issue").write_text("347\n")
    (cache / "worker_claude.stage").write_text("1/2\n")
    return environment, cache


def _stage_exit(environment):
    return subprocess.run(
        ["bash", str(DRIVER), "claude", "stage-exit"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_a_merge_commit_that_carries_the_stage_subject_closes_the_stage(tmp_path):
    environment, cache = _branch_with_a_merge(
        tmp_path, "stage 2/2: Make it pass", side_subject="a commit on the base"
    )
    result = _stage_exit(environment)
    assert "stage 2/2 was the last one" in result.stdout, result.stdout + result.stderr
    state = cache / "worker_claude.state"
    assert not state.is_file() or "CUT_BY_GUARD" not in state.read_text()


def test_a_stage_commit_that_arrived_from_the_base_is_still_not_this_branchs(tmp_path):
    """What `--first-parent` is for: the base merged in carries other issues' `stage N/M:` commits
    as a second parent, and an ordinary merge subject says nothing of a stage."""
    environment, cache = _branch_with_a_merge(
        tmp_path,
        "Merge branch 'origin/main' into claude/347-staged",
        side_subject="stage 2/2: another issue's stage",
    )
    result = _stage_exit(environment)
    assert "no new stage commit (still 1/2)" in result.stdout, result.stdout + result.stderr
    assert (
        (cache / "worker_claude.state")
        .read_text()
        .startswith("CUT_BY_GUARD reason=no_stage_commit")
    )
