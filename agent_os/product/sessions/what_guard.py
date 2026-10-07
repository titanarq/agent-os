"""The guard on the what: which pull requests are never merged automatically.

`docs/tree/dec-a-change-to-the-what-is-merged-only-on-the-owners-word.md`: a pull request that
touches a goal node or an evaluator is merged only on the owner's word. Here a pull request does
that when a changed file, on either side of the change, is

- a goal node under the tree root (a goal's verification is part of the goal's file), or
- a file the host listed in `tree.owner_only_paths` -- the other evaluators: the composition of the
  method battery, the thresholds of the indicators, the rule that tells what from how.

A file under the tree root that cannot be read as a record is treated as the what: a guard that
let an unreadable file through would be one a malformed goal could slip past.
"""

from __future__ import annotations

import fnmatch
import pathlib
from collections.abc import Callable
from dataclasses import dataclass

import yaml

from agent_os.product.tree.loader import split_frontmatter

BASE = "base"
HEAD = "head"
# (side, path) -> the file's text on that side, or None when it does not exist there.
FileReader = Callable[[str, str], str | None]


@dataclass(frozen=True)
class FileChange:
    path: str
    previous_path: str | None = None


@dataclass(frozen=True)
class WhatTouch:
    path: str
    reason: str


def read_frontmatter(text: str) -> tuple[dict, str] | None:
    """`(frontmatter, body)` of a record, or None when it is not a readable one."""
    parts = split_frontmatter(text)
    if parts is None:
        return None
    try:
        frontmatter = yaml.safe_load(parts[0])
    except yaml.YAMLError:
        return None
    return (frontmatter, parts[1]) if isinstance(frontmatter, dict) else None


def is_under(path: str, directory: str) -> bool:
    directory = directory.strip("/")
    return path == directory or path.startswith(directory + "/")


def _touches_a_goal(path: str, read_file: FileReader) -> str | None:
    for side in (BASE, HEAD):
        text = read_file(side, path)
        if text is None:
            continue
        document = read_frontmatter(text)
        if document is None:
            return "a file under the tree root that cannot be read as a record"
        if document[0].get("type") == "goal":
            return "a goal node"
    return None


def find_what_touches(
    changes: list[FileChange],
    *,
    tree_root: str,
    owner_only_paths: list[str],
    read_file: FileReader,
) -> list[WhatTouch]:
    touches: list[WhatTouch] = []
    for change in changes:
        for path in dict.fromkeys(p for p in (change.path, change.previous_path) if p):
            if any(fnmatch.fnmatchcase(path, pattern) for pattern in owner_only_paths):
                touches.append(WhatTouch(path, "an evaluator the host reserves to the owner"))
            elif is_under(path, tree_root) and pathlib.PurePosixPath(path).suffix == ".md":
                reason = _touches_a_goal(path, read_file)
                if reason:
                    touches.append(WhatTouch(path, reason))
    return touches
