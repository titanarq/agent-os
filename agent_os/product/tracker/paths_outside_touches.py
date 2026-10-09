"""The files a worker's branch changes outside the `touches` its ticket declared.

`worker_task.sh open-pr` asks it with the issue body (on stdin), the worktree it is about to publish
and the ref the branch is measured against, and appends the answer to the body of the pull request:

    python -m agent_os.product.tracker.paths_outside_touches --worktree DIR --base REF < issue-body

`touches` is the premise of `dec-dispatch-never-runs-two-tickets-on-the-same-code`: the start gate
lets two tickets run at once because their declared paths do not overlap. A worker that edits a file
beyond them can collide with a ticket running in parallel that the gate had no way to see. It is
listed and never refused (`docs/adr/2026-10-09-a-branch-outside-its-touches-is-listed-not-refused.md`):
the validator judges each file and says whether it could collide.

Prints nothing and exits 0 when the ticket declares no `touches` (a host whose tickets do not come
from a tree) or the branch stays inside them. A diff git cannot read is a line on stderr and exit 2:
the pull request is opened without the section, because a failure of this tool is no verdict.
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys
from collections.abc import Sequence

from agent_os import lib
from agent_os.product.dispatch.markers import parse_touched_paths
from agent_os.product.dispatch.touched_code import normalize_path

PROGRAM = "agent_os.product.tracker.paths_outside_touches"
CHECK_COULD_NOT_RUN = 2
SECTION_HEADING = "Files outside the ticket's `touches`"


def _is_within(path: str, covering_path: str) -> bool:
    return path == covering_path or path.startswith(covering_path + "/")


def paths_outside_touches(
    changed_paths: Sequence[str], declared_touches: Sequence[str], tree_root: str
) -> list[str]:
    """The changed paths no declared path covers (a directory covers what is under it). A ticket that
    declares nothing has no premise to be outside of, and the node files under `tree_root` are the
    worker's own write-back, which its prompt asks for."""
    covering_paths = [normalize_path(path) for path in declared_touches]
    if not covering_paths:
        return []
    node_files_root = normalize_path(tree_root)
    return [
        path
        for path in changed_paths
        if not any(_is_within(path, covering_path) for covering_path in covering_paths)
        and not (node_files_root and _is_within(path, node_files_root))
    ]


def describe_paths_outside_touches(
    declared_touches: Sequence[str], outside_paths: Sequence[str]
) -> str:
    """The section of the pull request body: what the ticket declared, and each file beyond it."""
    declared = ", ".join(f"`{path}`" for path in declared_touches)
    listed = "\n".join(f"- `{path}`" for path in outside_paths)
    return (
        f"## {SECTION_HEADING}\n\n"
        f"The ticket declared that it touches {declared}. This branch also changes:\n\n"
        f"{listed}\n\n"
        "Dispatch lets two tickets run at once when their `touches` do not overlap "
        "(`dec-dispatch-never-runs-two-tickets-on-the-same-code`), so a file beyond them can "
        "collide with a ticket running in parallel. The validator judges each one: justified or "
        "not, and whether it could collide.\n"
    )


def changed_paths_of_branch(worktree: pathlib.Path, base_ref: str) -> list[str]:
    """Every path `base_ref..HEAD` adds, modifies, deletes or renames (both names), as git names it."""
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(worktree),
            "diff",
            "--name-only",
            "--no-renames",
            "-z",
            f"{base_ref}...HEAD",
        ],
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"git diff {base_ref}...HEAD failed: {completed.stderr.decode().strip()}"
        )
    return [name.decode() for name in completed.stdout.split(b"\0") if name]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=PROGRAM)
    parser.add_argument("--worktree", required=True, type=pathlib.Path)
    parser.add_argument("--base", required=True, help="the branch is measured against this ref")
    arguments = parser.parse_args(argv)
    declared_touches = parse_touched_paths(sys.stdin.read())
    if not declared_touches:
        return 0
    try:
        tree_root = lib.load_agents_config(lib.DEFAULT_AGENTS_CONFIG).tree.root
        changed_paths = changed_paths_of_branch(arguments.worktree, arguments.base)
    except lib.CONFIG_LOAD_ERRORS as error:
        print(f"{PROGRAM}: {lib.config_load_failure(error)}", file=sys.stderr)
        return CHECK_COULD_NOT_RUN
    except RuntimeError as error:
        print(f"{PROGRAM}: the check could not run: {error}", file=sys.stderr)
        return CHECK_COULD_NOT_RUN
    outside_paths = paths_outside_touches(changed_paths, declared_touches, tree_root)
    if outside_paths:
        print(describe_paths_outside_touches(declared_touches, outside_paths))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
