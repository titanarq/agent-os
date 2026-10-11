"""`agent-os-tree in-works [--root DIR] [--json]`: the open issues and pull requests, per node.

Read-only. The tree root, the repository and the state labels come from the host's config, which
`agent_os.product.tree.cli` resolves and passes in. A `gh` failure exits 1 with the reason.
"""

from __future__ import annotations

import argparse
import json
import sys

from agent_os.product.board.in_works.derive import nodes_in_works
from agent_os.product.board.in_works.github_listing import (
    InWorksError,
    open_issues,
    open_pull_requests,
)


def run_in_works(
    args: argparse.Namespace,
    repository: str,
    state_labels: list[str],
    tree_root: str,
    program: str,
) -> int:
    try:
        works = nodes_in_works(
            open_issues(repository), open_pull_requests(repository), state_labels, tree_root
        )
    except InWorksError as error:
        print(f"{program}: {error}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(works, indent=2, ensure_ascii=False))
        return 0
    for node_id, found in works.items():
        issues = ", ".join(f"#{row['number']}" for row in found["issues"]) or "-"
        pulls = ", ".join(f"#{row['number']}" for row in found["pull_requests"]) or "-"
        print(f"{node_id}: issues {issues}; pull requests {pulls}")
    return 0
