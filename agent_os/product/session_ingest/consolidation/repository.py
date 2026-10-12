"""The git side of a consolidation: a throwaway worktree cut from the default branch as origin has it
now, the lines that name the use case, the commit, the push and the pull request."""

from __future__ import annotations

import contextlib
import pathlib
import subprocess
import tempfile
from collections.abc import Iterator

MAX_MENTION_LINES = 200


class RepositoryError(Exception):
    """A git or gh step failed; the message carries its stderr."""


def run(command: list[str], *, cwd: pathlib.Path, check: bool = True) -> str:
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    if check and completed.returncode != 0:
        raise RepositoryError(f"`{' '.join(command[:3])}` failed: {completed.stderr.strip()}")
    return completed.stdout


@contextlib.contextmanager
def worktree_on_default_branch(host_root: pathlib.Path, branch: str) -> Iterator[pathlib.Path]:
    """A worktree on a new `branch` at origin's default branch, removed whatever happens."""
    head = run(
        ["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"], cwd=host_root, check=False
    )
    default_branch = head.strip().removeprefix("origin/") or "main"
    run(["git", "fetch", "-q", "origin", default_branch], cwd=host_root)
    path = pathlib.Path(tempfile.mkdtemp(prefix="agent-os-consolidation.")) / "worktree"
    run(
        ["git", "worktree", "add", "-q", "-b", branch, str(path), f"origin/{default_branch}"],
        cwd=host_root,
    )
    try:
        yield path
    finally:
        run(["git", "worktree", "remove", "--force", str(path)], cwd=host_root, check=False)
        run(["git", "branch", "-D", branch], cwd=host_root, check=False)
        with contextlib.suppress(OSError):
            path.parent.rmdir()


def default_branch_of(worktree: pathlib.Path) -> str:
    head = run(
        ["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"], cwd=worktree, check=False
    )
    return head.strip().removeprefix("origin/") or "main"


def lines_naming(worktree: pathlib.Path, node_id: str, outside: str) -> str:
    """`path:line: text` for each tracked line that names the node, outside the tree folder."""
    found = run(
        ["git", "grep", "-n", "-F", node_id, "--", ".", f":(exclude){outside}"],
        cwd=worktree,
        check=False,
    ).splitlines()
    kept = found[:MAX_MENTION_LINES]
    if len(found) > len(kept):
        kept.append(f"... {len(found) - len(kept)} more lines left out")
    return "\n".join(kept)


def commit_and_push(worktree: pathlib.Path, path: pathlib.Path, branch: str, message: str) -> None:
    run(["git", "add", "--", str(path)], cwd=worktree)
    run(["git", "commit", "-q", "-m", message], cwd=worktree)
    run(["git", "push", "-q", "-u", "origin", branch], cwd=worktree)


def open_pull_request(worktree: pathlib.Path, repo: str, branch: str, title: str, body: str) -> str:
    """The pull request's URL."""
    return run(
        [
            "gh",
            "pr",
            "create",
            "--repo",
            repo,
            "--base",
            default_branch_of(worktree),
            "--head",
            branch,
            "--title",
            title,
            "--body",
            body,
        ],
        cwd=worktree,
    ).strip()


def comment_on_issue(repo: str, number: int, body: str, cwd: pathlib.Path) -> None:
    run(["gh", "issue", "comment", str(number), "--repo", repo, "--body", body], cwd=cwd)
