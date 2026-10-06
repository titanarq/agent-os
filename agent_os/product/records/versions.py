"""The versions a record carries, so a later reader can tell which method produced it.

`docs/AGENTOS_V2_PLAN.md` ("Recording conventions"): every record carries the model, the CLI
version and the method version, and the method version is the agent-os subtree commit plus the
digest of the prompt that ran. Without them a change in acceptance rate cannot be told from a change
of model, and a prompt edit leaves no trace in the data it changed.
"""

from __future__ import annotations

import hashlib
import pathlib
import re
import subprocess

GIT_TIMEOUT_SECONDS = 10
SUBTREE_SPLIT_LINE = re.compile(r"^git-subtree-split:\s*([0-9a-f]{40})\s*$", re.MULTILINE)
SUBTREE_DIRECTORY_LINE = re.compile(r"^git-subtree-dir:\s*(\S+)\s*$", re.MULTILINE)
SUBTREE_HISTORY_DEPTH = 200


def prompt_digest(text: str) -> str:
    """`sha256:` and 16 hex digits: enough to tell two prompts apart in a log."""
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()[:16]


def _git(directory: pathlib.Path, *arguments: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(directory), *arguments],
            capture_output=True,
            text=True,
            check=False,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return completed.stdout.strip() if completed.returncode == 0 else None


def agent_os_commit(agent_os_dir: pathlib.Path) -> str | None:
    """The agent-os commit this copy of the mechanism is at, or None when it cannot be told.

    In agent-os's own checkout (or a worktree of it) that is `HEAD`. In a host it is a
    `git subtree --squash` of the host's repository: the squash commit's message carries the
    upstream commit as `git-subtree-split:`, so the answer is the most recent one that names this
    directory. None -- never a guess -- when neither holds: a record may carry an unknown method
    version, but not an invented one."""
    if (agent_os_dir / ".git").exists():
        return _git(agent_os_dir, "rev-parse", "HEAD")
    top = _git(agent_os_dir, "rev-parse", "--show-toplevel")
    if top is None:
        return None
    try:
        relative = agent_os_dir.resolve().relative_to(pathlib.Path(top).resolve()).as_posix()
    except ValueError:
        return None
    history = _git(
        pathlib.Path(top),
        "log",
        f"-n{SUBTREE_HISTORY_DEPTH}",
        "--format=%x00%B",
        f"--grep=git-subtree-dir: {relative}",
    )
    for message in (history or "").split("\x00"):
        directory = SUBTREE_DIRECTORY_LINE.search(message)
        split = SUBTREE_SPLIT_LINE.search(message)
        if directory and split and directory.group(1).rstrip("/") == relative:
            return split.group(1)
    return None


def record_versions(
    *,
    model: str | None,
    cli_version: str | None,
    prompt_text: str,
    agent_os_dir: pathlib.Path,
) -> dict:
    """The `versions` object of a record. `cli_version` is what the CLI itself reported (None for a
    run that never started), `prompt_text` the exact prompt that ran."""
    return {
        "model": model,
        "cli_version": cli_version,
        "method_version": {
            "agent_os_commit": agent_os_commit(agent_os_dir),
            "prompt_digest": prompt_digest(prompt_text),
        },
    }
