"""The code a node touches, and whether two sets of paths touch the same code.

A node says what code it touches in one of two ways, and what dispatch compares is that
(`docs/tree/dec-dispatch-never-runs-two-tickets-on-the-same-code.md`). It may declare it, in its
`touches` field, and then the declaration decides and no prose is read. Otherwise what it knows
about its code is free text -- the `implementation` pointer and, once resolved, the `mechanism` --
and the paths named there are derived, which is a guess: any word with a slash or a file extension
is taken for a path. A node that names no path is unknown to the comparison, never a collision with
everything. The components the decision speaks of (`use:`) are not in the tree format yet; when they
are, their paths join here.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from agent_os.product.tree.models import MECHANISM_PENDING, Node

# A token is a path when it has a directory separator, or a file extension of at least two letters
# (`AGENTS.md`, not `e.g.` or `v1.2`). Anything around it -- quotes, a trailing comma -- is prose.
_TOKEN_RE = re.compile(r"[A-Za-z0-9_.\-]+(?:/[A-Za-z0-9_.\-]+)*/?")
_FILE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_\-]*\.[A-Za-z][A-Za-z0-9]+$")


def normalize_path(path: str) -> str:
    stripped = path.strip().rstrip("/.,;:")
    while stripped.startswith("./"):
        stripped = stripped[2:]
    return stripped


def paths_named_in(text: str) -> tuple[str, ...]:
    found: dict[str, None] = {}
    for token in _TOKEN_RE.findall(text or ""):
        candidate = normalize_path(token)
        if not candidate or candidate.startswith(".") and "/" not in candidate:
            continue
        if "/" in candidate or _FILE_NAME_RE.match(candidate):
            found[candidate] = None
    return tuple(found)


def _declared_path(path: str) -> str:
    """A declared path written the way a derived one is (no `./` in front, no `/` behind). Unlike
    prose, it has no trailing punctuation to strip, so `normalize_path` is not used."""
    while path.startswith("./"):
        path = path[2:]
    return path.rstrip("/")


def touched_paths_of(node: Node) -> tuple[str, ...]:
    """The node's `touches` when it has the field -- empty meaning no known code, and the prose not
    read -- else the paths named by its `implementation` and by its `mechanism` once it is written."""
    if node.touches is not None:
        return tuple(dict.fromkeys(_declared_path(path) for path in node.touches))
    texts = [node.implementation or ""]
    if node.mechanism and node.mechanism != MECHANISM_PENDING:
        texts.append(node.mechanism)
    found: dict[str, None] = {}
    for text in texts:
        found.update(dict.fromkeys(paths_named_in(text)))
    return tuple(found)


def _overlaps(first: str, second: str) -> bool:
    return first == second or first.startswith(second + "/") or second.startswith(first + "/")


def overlapping_paths(first: Iterable[str], second: Iterable[str]) -> list[str]:
    """The paths of `first` that are, or sit inside or above, a path of `second`."""
    others = [normalize_path(path) for path in second]
    return [path for path in first if any(_overlaps(normalize_path(path), o) for o in others)]
