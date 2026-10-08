"""The `Node-Change` trailers of a worker's branch, judged before its pull request is opened.

`worker_task.sh open-pr` asks it with the worktree it is about to publish and the ref the branch is
measured against. The host's CI runs the same question on the pull request afterwards
(`agent-os-tree trailers`), so a branch that fails here is a pull request that would be red the
moment it was born; it is cheaper to say so before it exists.

    python -m agent_os.product.tracker.branch_trailers --worktree DIR --base REF

Silent and exit 0 when the branch is sound, or when the worktree has no tree directory at all (a
host whose work does not come from a product tree). One line per defective commit on stdout and
exit 1 otherwise; a history git cannot read is a line on stderr and exit 2, never a pass.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from collections.abc import Sequence

from agent_os import lib
from agent_os.product.tree.trailers import TrailerDefect, TrailerError, check_node_change_trailers

PROGRAM = "agent_os.product.tracker.branch_trailers"
COMMITS_DEFECTIVE = 1
CHECK_COULD_NOT_RUN = 2


def branch_trailer_defects(
    worktree: pathlib.Path, tree_root: str, base_ref: str
) -> list[TrailerDefect]:
    """The defects of `base_ref..HEAD` in `worktree`, whose tree directory is `tree_root` under it.
    A worktree without that directory has no tree commit to judge."""
    root = worktree / tree_root
    if not root.is_dir():
        return []
    return check_node_change_trailers(root, base_ref, "HEAD")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=PROGRAM)
    parser.add_argument("--worktree", required=True, type=pathlib.Path)
    parser.add_argument("--base", required=True, help="the range starts after this ref")
    arguments = parser.parse_args(argv)
    try:
        tree_root = lib.load_agents_config(lib.DEFAULT_AGENTS_CONFIG).tree.root
    except lib.CONFIG_LOAD_ERRORS as error:
        print(f"{PROGRAM}: {lib.config_load_failure(error)}", file=sys.stderr)
        return CHECK_COULD_NOT_RUN
    try:
        defects = branch_trailer_defects(arguments.worktree, tree_root, arguments.base)
    except TrailerError as error:
        print(f"{PROGRAM}: the check could not run: {error}", file=sys.stderr)
        return CHECK_COULD_NOT_RUN
    for defect in defects:
        print(defect.describe())
    return COMMITS_DEFECTIVE if defects else 0


if __name__ == "__main__":
    raise SystemExit(main())
