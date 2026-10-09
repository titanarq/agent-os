"""`open-pr` lists, in the body of the pull request, the files the branch changes outside the
ticket's `touches`, so the validator can judge each one.

`touches` is what dispatch compares so that two tickets never run on the same code
(`dec-dispatch-never-runs-two-tickets-on-the-same-code`); a worker that edits a file beyond it can
collide with a ticket running in parallel that the gate let through. It is not refused, because a
refactor outside the declared paths is often the right call -- it is made visible.

The harness is `test_worker_task.py`'s own: a worktree with a real local origin, a stub `gh`, and no
backend anywhere.
"""

from __future__ import annotations

import subprocess

from test_worker_task import _git, _open_pr, worker_at_its_end  # noqa: F401

from agent_os.cli import AGENT_OS_DIR
from agent_os.product.tracker.paths_outside_touches import (
    SECTION_HEADING,
    describe_paths_outside_touches,
    paths_outside_touches,
)

TICKET_THAT_TOUCHES_THE_APP = (
    "## Objective\nbuild it\n\n<!-- node: fr-build-it -->\n<!-- touches: src/app -->\n"
)


def commit_files(worktree, *paths):
    for path in paths:
        target = worktree / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x = 1\n")
        _git("add", path, cwd=worktree)
    _git("commit", "-qm", "stage 1/1: the work", cwd=worktree)


def body_of_the_pull_request_created(calls):
    created = [line for line in calls.read_text().split("pr\tcreate") if "--body" in line]
    assert len(created) == 1, calls.read_text()
    return created[0]


def test_a_file_under_a_touched_directory_is_inside():
    assert (
        paths_outside_touches(["src/app/a.py", "src/app/deep/b.py"], ["src/app"], "product") == []
    )


def test_a_touched_file_is_inside_and_a_sibling_of_it_is_not():
    outside = paths_outside_touches(
        ["web/entry.html", "web/other.html"], ["web/entry.html"], "product"
    )
    assert outside == ["web/other.html"]


def test_a_directory_name_that_only_shares_a_prefix_is_outside():
    assert paths_outside_touches(["src/application.py"], ["src/app"], "product") == [
        "src/application.py"
    ]


def test_the_declared_paths_are_read_the_way_dispatch_reads_them():
    assert paths_outside_touches(["src/app/a.py"], ["./src/app/"], "product") == []


def test_the_node_files_under_the_tree_root_are_never_listed():
    """A worker writes back to its own node, which the prompt asks of it."""
    assert paths_outside_touches(["product/fr-build-it.md"], ["src/app"], "product") == []


def test_a_ticket_that_declares_no_touches_has_nothing_to_be_outside_of():
    assert paths_outside_touches(["anything.py"], [], "product") == []


def test_the_description_names_the_declared_paths_and_every_file_outside_them():
    text = describe_paths_outside_touches(["src/app"], ["src/other/b.py", "README.md"])
    assert "`src/app`" in text
    assert "- `src/other/b.py`" in text
    assert "- `README.md`" in text
    assert "dec-dispatch-never-runs-two-tickets-on-the-same-code" in text


def test_open_pr_lists_in_the_pull_request_the_files_outside_the_touches(worker_at_its_end):  # noqa: F811
    environment, worktree, _remote, _cache, calls = worker_at_its_end
    environment["GH_STUB_BODY"] = TICKET_THAT_TOUCHES_THE_APP
    commit_files(worktree, "src/app/inside.py", "src/other/outside.py")

    result = _open_pr(environment)

    assert result.returncode == 0, result.stdout + result.stderr
    body = body_of_the_pull_request_created(calls)
    assert "Closes #348" in body
    assert "- `src/other/outside.py`" in body
    assert "- `delivered.py`" in body, "the fixture's own first commit is outside `src/app` too"
    assert "inside.py" not in body


def test_open_pr_says_nothing_of_touches_when_the_branch_stays_inside_them(worker_at_its_end):  # noqa: F811
    environment, worktree, _remote, _cache, calls = worker_at_its_end
    environment["GH_STUB_BODY"] = TICKET_THAT_TOUCHES_THE_APP.replace(
        "src/app", "src/app, delivered.py"
    )
    commit_files(worktree, "src/app/inside.py")

    result = _open_pr(environment)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Files outside" not in body_of_the_pull_request_created(calls)


def test_open_pr_says_nothing_of_touches_when_the_ticket_declares_none(worker_at_its_end):  # noqa: F811
    environment, worktree, _remote, _cache, calls = worker_at_its_end
    commit_files(worktree, "src/other/outside.py")

    result = _open_pr(environment)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Files outside" not in body_of_the_pull_request_created(calls)


def test_open_pr_still_opens_the_pull_request_whatever_the_branch_touches(worker_at_its_end):  # noqa: F811
    """Listed, never refused: nothing is blocked, pushed late or left unlabelled over it."""
    environment, worktree, remote, cache, calls = worker_at_its_end
    environment["GH_STUB_BODY"] = TICKET_THAT_TOUCHES_THE_APP
    commit_files(worktree, "src/other/outside.py")

    _open_pr(environment)

    assert "labels[]=status:ai-completed" in calls.read_text()
    assert (cache / "worker_claude.state").read_text().splitlines()[0] == "STARTED"
    assert (
        subprocess.run(
            ["git", "-C", str(remote), "rev-parse", "--verify", "claude/348-pr"],
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


def test_the_validator_prompt_asks_for_a_verdict_on_each_file_of_that_section():
    prompt = " ".join((AGENT_OS_DIR / "prompts" / "validator.md").read_text().split())
    assert f"a section `{SECTION_HEADING}`" in prompt
    assert "Judge each listed file" in prompt
    assert "justified" in prompt and "could collide with what runs in parallel" in prompt
