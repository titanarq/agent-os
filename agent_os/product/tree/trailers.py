"""The `Node-Change` trailer: how a change to the product tree says why it was made.

Every commit that touches a file under the host's tree root carries exactly one trailer
`Node-Change: usage | rework | owner` (`docs/AGENTOS_V2_PLAN.md`, recording conventions):

- `usage`  -- feedback from using the product taught something the node did not say.
- `rework` -- a correction after a validation or a rejection showed the node was wrong.
- `owner`  -- the owner's own word changed it.

The history of those commits is the evidence the method is later judged by, so a commit without
the trailer is a red check and not a habit asked for. This module only reads git: it opens no
network and no backend.
"""

from __future__ import annotations

import pathlib
import subprocess
from dataclasses import dataclass

TRAILER_KEY = "Node-Change"
NODE_CHANGE_VALUES = ("usage", "rework", "owner")

MISSING_TRAILER = "missing-node-change"
UNKNOWN_VALUE = "unknown-node-change"
MULTIPLE_TRAILERS = "multiple-node-change"

_FIELD_SEPARATOR = "\x1f"
_RECORD_SEPARATOR = "\x1e"
_VALUE_SEPARATOR = "\x1d"


class TrailerError(Exception):
    """The premise of the check does not hold: no git repository, or a range git cannot resolve.
    A check that cannot read the history must fail, never pass over nothing."""


@dataclass(frozen=True)
class TrailerDefect:
    commit: str
    subject: str
    code: str
    message: str


def _run_git(directory: pathlib.Path, *arguments: str) -> str:
    try:
        completed = subprocess.run(
            ["git", *arguments], cwd=directory, check=True, capture_output=True, text=True
        )
    except FileNotFoundError as error:
        raise TrailerError("git is not installed") from error
    except subprocess.CalledProcessError as error:
        raise TrailerError(
            f"git {' '.join(arguments[:2])} failed: {error.stderr.strip()}"
        ) from error
    return completed.stdout


def _nearest_existing_directory(path: pathlib.Path) -> pathlib.Path:
    candidate = path.resolve()
    while not candidate.is_dir():
        if candidate == candidate.parent:
            raise TrailerError(f"no directory above {path} exists")
        candidate = candidate.parent
    return candidate


def _commits_touching(
    tree_root: pathlib.Path, base: str, head: str
) -> list[tuple[str, str, list[str]]]:
    """(sha, subject, every `Node-Change` value) of each non-merge commit of `base..head` that
    changes a path under `tree_root`; git itself narrows the log to that pathspec."""
    resolved = tree_root.resolve()
    working_directory = _nearest_existing_directory(resolved)
    toplevel = pathlib.Path(_run_git(working_directory, "rev-parse", "--show-toplevel").strip())
    pathspec = resolved.relative_to(toplevel.resolve()).as_posix() or "."
    log_format = (
        f"{_RECORD_SEPARATOR}%H{_FIELD_SEPARATOR}%s{_FIELD_SEPARATOR}"
        f"%(trailers:key={TRAILER_KEY},valueonly=true,unfold=true,separator=%x1d)"
    )
    output = _run_git(
        toplevel,
        "log",
        "--no-merges",
        f"--format={log_format}",
        f"{base}..{head}",
        "--",
        pathspec,
    )
    commits = []
    for record in output.split(_RECORD_SEPARATOR)[1:]:
        sha, subject, joined_values = record.split(_FIELD_SEPARATOR, 2)
        values = [
            value.strip()
            for value in joined_values.strip().split(_VALUE_SEPARATOR)
            if value.strip()
        ]
        commits.append((sha, subject, values))
    return commits


def check_node_change_trailers(
    tree_root: pathlib.Path | str, base: str, head: str = "HEAD"
) -> list[TrailerDefect]:
    """One defect per commit of `base..head` touching `tree_root` whose trailer is absent, repeated
    or not one of `NODE_CHANGE_VALUES`."""
    defects = []
    for sha, subject, values in _commits_touching(pathlib.Path(tree_root), base, head):
        if not values:
            code, message = MISSING_TRAILER, f"touches the tree without a `{TRAILER_KEY}:` trailer"
        elif len(values) > 1:
            code, message = (
                MULTIPLE_TRAILERS,
                f"carries {len(values)} `{TRAILER_KEY}:` trailers, one expected",
            )
        elif values[0] not in NODE_CHANGE_VALUES:
            allowed = " | ".join(NODE_CHANGE_VALUES)
            code, message = UNKNOWN_VALUE, f"`{TRAILER_KEY}: {values[0]}` is not one of {allowed}"
        else:
            continue
        defects.append(TrailerDefect(sha, subject, code, message))
    return defects
