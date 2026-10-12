"""The paths a branch changes: the three-dot diff against the merge-base with its base."""

from __future__ import annotations

import pathlib
import subprocess

from agent_os.quality.git_snapshots import GitError, merge_base_with_head


def run_git(repository: pathlib.Path, *arguments: str) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(repository), *arguments], capture_output=True, check=False
    )
    if completed.returncode != 0:
        raise GitError(f"git {' '.join(arguments)} failed: {completed.stderr.decode().strip()}")
    return completed.stdout


def changed_paths(
    repository: pathlib.Path, base_reference: str, head_reference: str = "HEAD"
) -> list[str]:
    """Everything `base...head` adds, modifies or deletes (the head is the checkout's `HEAD` unless
    a caller names another commit it holds); a rename is reported as both of its paths
    (`--no-renames`). A missing `.git` or an unresolvable base raises `GitError`: the premise
    is missing, and "nothing changed" would skip every test."""
    merge_base = merge_base_with_head(repository, base_reference, head_reference)
    output = run_git(
        repository, "diff", "--name-only", "--no-renames", "-z", f"{merge_base}...{head_reference}"
    )
    return sorted(name.decode() for name in output.split(b"\0") if name)
