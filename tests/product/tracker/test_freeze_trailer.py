"""A freeze commit that touches the product tree carries the `Node-Change` trailer the host's CI asks of it.

`open-pr` freezes what a finished run left uncommitted (`WIP: cut by guard (before_merge)`) and the
guard's cut freezes a run's work the same way. Both commits used to touch the tree with no trailer,
so since the check of #139 `open-pr` refused a branch only because of its own freeze. The freeze
cannot say why the node changed, so it repeats the reason of the branch it freezes: the nearest
`usage` or `rework` already on it, and `usage` -- what a worker writes while building -- otherwise.

The harness is `test_worker_task.py`'s own: a worktree with a real local origin, a stub `gh`, and no
backend anywhere.
"""

from __future__ import annotations

import subprocess

from test_branch_trailers import commit_to_the_tree
from test_worker_task import (  # noqa: F401
    DRIVER,
    ROOT,
    _git,
    _open_pr,
    _subjects,
    worker_at_its_end,
)

from agent_os.product.tree.trailers import check_node_change_trailers

FREEZE_SUBJECT = "WIP: cut by guard (before_merge)"


def leave_a_tree_edit_uncommitted(worktree):
    node_file = worktree / "product" / "fr-write-it-back.md"
    node_file.parent.mkdir(exist_ok=True)
    node_file.write_text(node_file.read_text() + "left behind\n" if node_file.exists() else "x\n")


def trailer_values_of_the_newest_freeze(worktree):
    values = subprocess.run(
        [
            "git", "-C", str(worktree), "log", "-1", "--grep", "WIP: cut by guard",
            "--format=%(trailers:key=Node-Change,valueonly=true,unfold=true)",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout  # fmt: skip
    return values.split()


def freeze(environment, reason="before_merge"):
    return subprocess.run(
        ["bash", str(DRIVER), "claude", "freeze", reason],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_open_pr_is_not_blocked_by_the_trailer_of_its_own_pre_merge_freeze(worker_at_its_end):  # noqa: F811
    """Replaces `test_open_pr_judges_the_freeze_it_makes_before_merging_too`, which pinned the
    defect: a freeze touching the tree with no trailer, and the branch refused for it. The check
    still runs after the freeze -- it just finds nothing to refuse."""
    environment, worktree, _remote, cache, calls = worker_at_its_end
    commit_to_the_tree(worktree, "stage 1/1: write the node back", "Node-Change: usage")
    leave_a_tree_edit_uncommitted(worktree)

    result = _open_pr(environment)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _subjects(worktree)[0] == FREEZE_SUBJECT
    assert trailer_values_of_the_newest_freeze(worktree) == ["usage"]
    assert "pr\tcreate" in calls.read_text()
    assert (cache / "worker_claude.state").read_text().splitlines()[0] == "STARTED"
    assert check_node_change_trailers(worktree / "product", "origin/main", "HEAD") == []


def test_the_freeze_repeats_the_rework_of_the_branch_it_freezes(worker_at_its_end):  # noqa: F811
    environment, worktree, _remote, _cache, _calls = worker_at_its_end
    commit_to_the_tree(worktree, "stage 1/1: fix what the review asked", "Node-Change: rework")
    leave_a_tree_edit_uncommitted(worktree)

    assert _open_pr(environment).returncode == 0

    assert trailer_values_of_the_newest_freeze(worktree) == ["rework"]


def test_the_freeze_never_repeats_the_owners_word_an_agent_does_not_write(worker_at_its_end):  # noqa: F811
    environment, worktree, _remote, _cache, _calls = worker_at_its_end
    commit_to_the_tree(worktree, "the owner's own edit", "Node-Change: owner")
    leave_a_tree_edit_uncommitted(worktree)

    freeze(environment, "worker_cut")

    assert trailer_values_of_the_newest_freeze(worktree) == ["usage"]


def test_a_freeze_of_a_branch_with_no_trailer_yet_says_usage(worker_at_its_end):  # noqa: F811
    environment, worktree, _remote, _cache, _calls = worker_at_its_end
    leave_a_tree_edit_uncommitted(worktree)

    result = freeze(environment)

    assert result.returncode == 0, result.stdout + result.stderr
    assert trailer_values_of_the_newest_freeze(worktree) == ["usage"]


def test_a_freeze_that_names_the_files_it_swept_in_keeps_the_trailer_in_the_last_paragraph(
    worker_at_its_end,  # noqa: F811
):
    environment, worktree, _remote, _cache, _calls = worker_at_its_end
    (worktree / "product").mkdir()
    (worktree / "product" / "fr-new-node.md").write_text("a node the stage never added\n")

    assert freeze(environment).returncode == 0

    body = _git_output("log", "-1", "--format=%b", cwd=worktree)
    assert "fr-new-node.md" in body
    assert trailer_values_of_the_newest_freeze(worktree) == ["usage"]


def test_a_freeze_that_touches_nothing_in_the_tree_carries_no_trailer(worker_at_its_end):  # noqa: F811
    environment, worktree, _remote, _cache, _calls = worker_at_its_end
    (worktree / "delivered.py").write_text("x = 2\n")

    assert freeze(environment).returncode == 0

    assert trailer_values_of_the_newest_freeze(worktree) == []
    assert "Node-Change" not in _git_output("log", "-1", "--format=%B", cwd=worktree)


def _git_output(*arguments, cwd):
    return subprocess.run(
        ["git", *arguments], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


def test_a_freeze_without_a_readable_config_still_commits_the_work_and_only_loses_the_trailer(
    worker_at_its_end,  # noqa: F811
):
    from agent_os.product.tracker.freeze_commit import commit_staged_work

    _environment, worktree, _remote, _cache, _calls = worker_at_its_end
    leave_a_tree_edit_uncommitted(worktree)
    _git("add", "product", cwd=worktree)

    assert commit_staged_work(worktree, FREEZE_SUBJECT, "", None) == 0

    assert _subjects(worktree)[0] == FREEZE_SUBJECT
    assert trailer_values_of_the_newest_freeze(worktree) == []
