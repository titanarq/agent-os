"""The commit of a freeze: a run's leftover work, committed by the mechanism and not by the agent.

`worker_task.sh` freezes a tree in two cases -- the guard cut a run, or `open-pr` found a finished
run's work uncommitted before merging the base in -- as a `WIP: cut by guard (<reason>)` commit.
When that commit touches the product tree it needs the `Node-Change` trailer the host's CI asks of
every such commit, or the pull request is red (and `open-pr` refuses it) for a commit no agent wrote.

A freeze cannot know why the node changed, so it repeats the reason of the branch it freezes: the
nearest `usage` or `rework` already on the branch, and `usage` -- what a worker writes while it
builds its node -- when there is none. Never `owner`: that is the owner's own word, an agent's
freeze is not it. The history stays the record of why each node changed, with the freeze saying
what the branch around it said.

    python -m agent_os.product.tracker.freeze_commit --worktree DIR --subject S [--body TEXT]

Commits what is staged in DIR, and never refuses to: a config it cannot read only costs the trailer
(said on stderr), because losing a run's work to a missing trailer is the worse failure.
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys
from collections.abc import Sequence

from agent_os import lib
from agent_os.product.tree.trailers import NODE_CHANGE_VALUES, OWNER_VALUE, TRAILER_KEY

DEFAULT_VALUE = "usage"
# The values an agent may write; the branch's reason is searched among these only.
AGENT_VALUES = tuple(value for value in NODE_CHANGE_VALUES if value != OWNER_VALUE)
BASE_REFS = ("origin/main", "main")
PROGRAM = "agent_os.product.tracker.freeze_commit"


def _git(worktree: pathlib.Path, *arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(worktree), *arguments], capture_output=True, text=True, check=False
    )


def staged_work_touches(worktree: pathlib.Path, tree_root: str) -> bool:
    staged = _git(worktree, "diff", "--cached", "--name-only", "--", tree_root)
    return bool(staged.stdout.strip())


def reason_of_the_branch(worktree: pathlib.Path) -> str:
    """The newest `usage` or `rework` among the commits `HEAD` has and the base lacks, or
    `DEFAULT_VALUE`. Without a base to measure from there is no branch to read, and no guess."""
    for base_ref in BASE_REFS:
        fork_point = _git(worktree, "merge-base", base_ref, "HEAD")
        if fork_point.returncode != 0:
            continue
        values = _git(
            worktree,
            "log",
            "--no-merges",
            f"--format=%(trailers:key={TRAILER_KEY},valueonly=true,unfold=true,separator=%x20)",
            f"{fork_point.stdout.strip()}..HEAD",
        ).stdout.split()
        return next((value for value in values if value in AGENT_VALUES), DEFAULT_VALUE)
    return DEFAULT_VALUE


def commit_staged_work(
    worktree: pathlib.Path, subject: str, body: str, tree_root: str | None
) -> int:
    """`git commit` of the index. The trailer is its own, last paragraph, so git reads it whatever
    the body says."""
    paragraphs = [subject, body]
    if tree_root is not None and staged_work_touches(worktree, tree_root):
        paragraphs.append(f"{TRAILER_KEY}: {reason_of_the_branch(worktree)}")
    message_arguments = [flag for text in paragraphs if text for flag in ("-m", text)]
    return _git(worktree, "commit", "-q", *message_arguments).returncode


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=PROGRAM)
    parser.add_argument("--worktree", required=True, type=pathlib.Path)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--body", default="")
    arguments = parser.parse_args(argv)
    try:
        tree_root = lib.load_agents_config(lib.DEFAULT_AGENTS_CONFIG).tree.root
    except lib.CONFIG_LOAD_ERRORS as error:
        print(
            f"{PROGRAM}: committed without a {TRAILER_KEY} trailer, the config did not load: "
            f"{lib.config_load_failure(error)}",
            file=sys.stderr,
        )
        tree_root = None
    return commit_staged_work(arguments.worktree, arguments.subject, arguments.body, tree_root)


if __name__ == "__main__":
    raise SystemExit(main())
