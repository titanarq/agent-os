"""The paths a built node names in its `implementation` still exist in the repository.

A node's `implementation` is where the built thing lives. Another ticket may move or delete that
code, and the pointer then sends the next reader -- an agent given the node's slice, the owner -- to
a file that is not there: in the first v2 host two nodes named an `entry.html` another ticket had
deleted, and nothing was red. A lesson that only lives in a prompt gets forgotten, so it is a check
(`docs/tree/dec-memory-is-files-in-git-and-a-lesson-climbs-to-a-check.md`), run by `agent-os-tree
validate` and by a host's CI after it.

`implementation` is prose, so the check is built for precision and not for recall: a false positive
turns a sound tree red, a false negative only leaves today's blindness. It looks at

- nodes that are `implemented` or `hardened`: before that the code a node names may not exist yet;
- words that carry a `/`, never a bare file name: `entry.html` may be relative to a directory named
  earlier in the sentence, and a word like `http.client` is not a file;
- those that start at something the repository root holds (`web/...` when `web/` exists): a word
  like `answers/puntal_client.py` after `web/app/shell/` is relative to that directory, and nothing
  here can resolve it.

What survives is a path the node wrote from the root, whose first folder is real and whose rest is
not: a pointer that went stale.
"""

from __future__ import annotations

import pathlib
import subprocess

from agent_os.product.dispatch.touched_code import paths_named_in
from agent_os.product.tree.loader import Defect, Tree
from agent_os.product.tree.models import Node

IMPLEMENTATION_PATH_MISSING = "implementation-path-missing"
STATES_WITH_BUILT_CODE = ("implemented", "hardened")


def repository_root_of(directory: pathlib.Path) -> pathlib.Path | None:
    """The git checkout `directory` belongs to, or None when it belongs to none -- a tree under a
    temporary directory, which has no repository to hold its paths against."""
    completed = subprocess.run(
        ["git", "-C", str(directory), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    return pathlib.Path(completed.stdout.strip()).resolve()


def _missing_paths_of(node: Node, repository_root: pathlib.Path) -> list[str]:
    missing = []
    for path in paths_named_in(node.implementation or ""):
        first_folder, separator, _rest = path.partition("/")
        if not separator or not (repository_root / first_folder).exists():
            continue
        if not (repository_root / path).exists():
            missing.append(path)
    return missing


def check_implementation_paths(tree: Tree, repository_root: pathlib.Path) -> list[Defect]:
    defects = []
    for node in tree.nodes.values():
        if node.state not in STATES_WITH_BUILT_CODE:
            continue
        for path in _missing_paths_of(node, repository_root):
            defects.append(
                Defect(
                    tree.paths[node.id],
                    IMPLEMENTATION_PATH_MISSING,
                    f"`implementation` names {path}, which does not exist in the repository",
                )
            )
    return defects
