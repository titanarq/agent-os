"""`open-pr` judges the `Node-Change` trailers of the worker's branch before it opens the pull request.

A worker wrote `Node-Change: usage`, a blank line and `Co-Authored-By:`; git reads only the last
paragraph as trailers, so the host's CI check and `agent-os-tree trailers` found the trailer absent
and the pull request was red the moment it was born. The driver now asks the same question first and
refuses to announce such a branch as ready.

The harness is `test_worker_task.py`'s own: a worktree with a real local origin, a stub `gh`, and no
backend anywhere.
"""

from __future__ import annotations

import subprocess

from test_worker_task import _git, _open_pr, _subjects, worker_at_its_end  # noqa: F401

from agent_os.product.tracker.branch_trailers import branch_trailer_defects

CO_AUTHOR_LINE = "Co-Authored-By: A Worker <noreply@example.invalid>"
BLOCKED_STATE = "BLOCKED reason=malformed_node_change_trailer branch=claude/348-pr"


def commit_to_the_tree(worktree, subject, *trailer_paragraphs):
    """One commit that writes a node file; every extra argument is a paragraph of the message, so
    two of them are two paragraphs with a blank line between, as `git commit -m -m` writes them."""
    node_file = worktree / "product" / "fr-write-it-back.md"
    node_file.parent.mkdir(exist_ok=True)
    node_file.write_text(node_file.read_text() + "a line\n" if node_file.exists() else "a line\n")
    _git("add", "product/fr-write-it-back.md", cwd=worktree)
    message_arguments = [
        argument for text in (subject, *trailer_paragraphs) for argument in ("-m", text)
    ]
    _git("commit", "-q", *message_arguments, cwd=worktree)


def was_pushed(remote):
    return (
        subprocess.run(
            ["git", "-C", str(remote), "rev-parse", "--verify", "claude/348-pr"],
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


def test_open_pr_refuses_a_trailer_cut_off_from_the_last_paragraph(worker_at_its_end):  # noqa: F811
    environment, worktree, remote, cache, calls = worker_at_its_end
    commit_to_the_tree(
        worktree, "stage 1/1: write the node back", "Node-Change: usage", CO_AUTHOR_LINE
    )

    result = _open_pr(environment)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "misplaced-node-change" in result.stdout, result.stdout
    assert "stage 1/1: write the node back" in result.stdout, result.stdout
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
    # The issue carries the command's own words and what unblocks the branch.
    assert "misplaced-node-change" in recorded
    assert "stage 1/1: write the node back" in recorded
    assert "git interpret-trailers --parse" in recorded
    assert not was_pushed(remote), "a branch with a malformed trailer was pushed"


def test_open_pr_leaves_the_malformed_commit_as_the_worker_wrote_it(worker_at_its_end):  # noqa: F811
    """Refused, not repaired: rewriting a commit already made is a rewrite and this step rewrites
    nothing -- the same line `open-pr` already holds for the diary (#407)."""
    environment, worktree, _remote, _cache, _calls = worker_at_its_end
    commit_to_the_tree(
        worktree, "stage 1/1: write the node back", "Node-Change: usage", CO_AUTHOR_LINE
    )
    head_before = subprocess.run(
        ["git", "-C", str(worktree), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    _open_pr(environment)

    head_after = subprocess.run(
        ["git", "-C", str(worktree), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert head_after == head_before
    assert _subjects(worktree)[0] == "stage 1/1: write the node back"


def test_open_pr_refuses_a_commit_that_touches_the_tree_with_no_trailer_at_all(worker_at_its_end):  # noqa: F811
    environment, worktree, _remote, cache, calls = worker_at_its_end
    commit_to_the_tree(worktree, "stage 1/1: write the node back")

    result = _open_pr(environment)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "missing-node-change" in result.stdout, result.stdout
    assert (cache / "worker_claude.state").read_text().splitlines()[0] == BLOCKED_STATE
    assert "pr\tcreate" not in calls.read_text()


def test_open_pr_opens_the_pull_request_when_the_trailer_shares_its_block_with_the_co_author(
    worker_at_its_end,  # noqa: F811
):
    environment, worktree, _remote, cache, calls = worker_at_its_end
    commit_to_the_tree(
        worktree, "stage 1/1: write the node back", f"Node-Change: usage\n{CO_AUTHOR_LINE}"
    )

    result = _open_pr(environment)

    assert result.returncode == 0, result.stdout + result.stderr
    recorded = calls.read_text()
    assert "pr\tcreate" in recorded, recorded
    assert "labels[]=status:ai-completed" in recorded, recorded
    assert (cache / "worker_claude.state").read_text().splitlines()[0] == "STARTED"


def test_open_pr_goes_through_once_the_commit_is_repaired_and_clears_the_blocked_line(
    worker_at_its_end,  # noqa: F811
):
    """What the issue comment asks of whoever picks the branch up: fix the message, run `open-pr`
    again. The earlier `BLOCKED` line must not outlive the pull request it was about."""
    environment, worktree, _remote, cache, calls = worker_at_its_end
    commit_to_the_tree(
        worktree, "stage 1/1: write the node back", "Node-Change: usage", CO_AUTHOR_LINE
    )
    assert _open_pr(environment).returncode == 1

    _git(
        "commit",
        "-q",
        "--amend",
        "-m",
        "stage 1/1: write the node back",
        "-m",
        f"Node-Change: usage\n{CO_AUTHOR_LINE}",
        cwd=worktree,
    )
    result = _open_pr(environment)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "pr\tcreate" in calls.read_text()
    assert (cache / "worker_claude.state").read_text().splitlines() == [
        "DONE",
        "issue=348 label=status:ai-completed",
    ]


def test_open_pr_judges_the_freeze_it_makes_before_merging_too(worker_at_its_end):  # noqa: F811
    """A worker that left a node edit uncommitted gets it frozen in a `WIP: cut by guard` commit so
    the base can be merged, and that commit touches the tree without a trailer: the pull request it
    would travel in is red, so the branch is refused with the commit named."""
    environment, worktree, _remote, _cache, calls = worker_at_its_end
    commit_to_the_tree(
        worktree, "stage 1/1: write the node back", f"Node-Change: usage\n{CO_AUTHOR_LINE}"
    )
    (worktree / "product" / "fr-write-it-back.md").write_text("an edit nobody committed\n")

    result = _open_pr(environment)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "WIP: cut by guard (before_merge)" in result.stdout, result.stdout
    assert "pr\tcreate" not in calls.read_text()


def test_a_worktree_with_no_tree_directory_has_nothing_to_judge(tmp_path):
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    assert branch_trailer_defects(tmp_path, "product", "HEAD") == []


def test_open_pr_refuses_the_owners_word_in_a_commit_the_worker_wrote(worker_at_its_end):  # noqa: F811
    """`owner` is the owner's own word. A worker wrote it when it touched its node at the end of a
    ticket, and a well-formed trailer is not enough: the commit is an agent's."""
    environment, worktree, remote, cache, calls = worker_at_its_end
    commit_to_the_tree(
        worktree, "stage 1/1: write the node back", f"Node-Change: owner\n{CO_AUTHOR_LINE}"
    )

    result = _open_pr(environment)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "owner-word-by-agent" in result.stdout, result.stdout
    assert (cache / "worker_claude.state").read_text().splitlines()[0] == BLOCKED_STATE
    recorded = calls.read_text()
    assert "pr\tcreate" not in recorded, recorded
    assert "labels[]=status:blocked-on-human" in recorded, recorded
    assert not was_pushed(remote)
