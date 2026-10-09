"""Reads the two sides of the ratchet out of git: a revision's tree, and the checkout as it is."""

from __future__ import annotations

import pathlib
import subprocess

from agent_os.quality.ratchet import RepositorySnapshot


class GitError(RuntimeError):
    """A git command the check depends on failed; its message says what to do about it."""


def _git_output(repository: pathlib.Path, *arguments: str) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(repository), *arguments], capture_output=True, check=False
    )
    if completed.returncode != 0:
        raise GitError(f"git {' '.join(arguments)} failed: {completed.stderr.decode().strip()}")
    return completed.stdout


def git_toplevel_of(directory: pathlib.Path) -> pathlib.Path:
    """The root of the checkout `directory` belongs to -- a linked worktree's own root, never the
    main checkout it was made from -- and an error when it belongs to none."""
    return pathlib.Path(_git_output(directory, "rev-parse", "--show-toplevel").decode().strip())


def count_lines(content: bytes) -> int:
    """A binary file has no lines to speak of, so it counts as none."""
    if b"\0" in content:
        return 0
    return content.count(b"\n") + (1 if content and not content.endswith(b"\n") else 0)


def _split_null_separated(output: bytes) -> frozenset[str]:
    return frozenset(name.decode() for name in output.split(b"\0") if name)


def snapshot_of_checkout(repository: pathlib.Path) -> RepositorySnapshot:
    """What git tracks in the working tree; a tracked path deleted from disk is not counted."""
    tracked = _split_null_separated(_git_output(repository, "ls-files", "-z"))
    present = frozenset(path for path in tracked if (repository / path).is_file())

    def count_lines_of_checked_out_file(path: str) -> int:
        return count_lines((repository / path).read_bytes())

    return RepositorySnapshot(present, count_lines_of_checked_out_file)


def snapshot_of_revision(repository: pathlib.Path, revision: str) -> RepositorySnapshot:
    tracked = _split_null_separated(
        _git_output(repository, "ls-tree", "-r", "-z", "--name-only", revision)
    )

    def count_lines_of_committed_file(path: str) -> int:
        return count_lines(_git_output(repository, "show", f"{revision}:{path}"))

    return RepositorySnapshot(tracked, count_lines_of_committed_file)


def merge_base_with_head(repository: pathlib.Path, base_reference: str) -> str:
    try:
        return _git_output(repository, "merge-base", base_reference, "HEAD").decode().strip()
    except GitError as error:
        raise GitError(
            f"no merge-base between {base_reference} and HEAD ({error}); in CI the checkout "
            "needs `fetch-depth: 0` so the history that joins the two is present"
        ) from error
