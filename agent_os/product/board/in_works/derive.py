"""Which node each open issue and pull request is on, over plain rows and nothing else.

An issue is on the node its `<!-- node: <id> -->` marker names. A pull request is on the node of
every issue it closes (`Closes #N`, read as `tracker/pull_request_checks.py` reads it) and on every
node whose file `<tree root>/<id>.md` it changes. A node with nothing open is absent from the map.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence

from agent_os.product.dispatch.markers import parse_node_marker
from agent_os.product.tracker.pull_request_checks import CLOSES_ISSUE_PATTERN


def _status_label(issue: dict, state_labels: Collection[str]) -> str | None:
    held = [label["name"] for label in issue.get("labels") or [] if label["name"] in state_labels]
    return held[0] if held else None


def _node_file_id(path: str, tree_root: str) -> str | None:
    prefix = tree_root.rstrip("/") + "/"
    if not (path.startswith(prefix) and path.endswith(".md")):
        return None
    name = path[len(prefix) : -len(".md")]
    return name if name and "/" not in name else None


def nodes_in_works(
    issues: Sequence[dict],
    pull_requests: Sequence[dict],
    state_labels: Collection[str],
    tree_root: str,
) -> dict[str, dict]:
    works: dict[str, dict] = {}
    node_of_issue: dict[int, str] = {}

    def entry(node_id: str) -> dict:
        return works.setdefault(node_id, {"issues": [], "pull_requests": []})

    for issue in sorted(issues, key=lambda row: row["number"]):
        node_id = parse_node_marker(issue.get("body") or "")
        if node_id is None:
            continue
        node_of_issue[issue["number"]] = node_id
        entry(node_id)["issues"].append(
            {"number": issue["number"], "status": _status_label(issue, state_labels)}
        )

    for pull_request in sorted(pull_requests, key=lambda row: row["number"]):
        closed = [
            int(match["issue"])
            for match in CLOSES_ISSUE_PATTERN.finditer(pull_request.get("body") or "")
        ]
        touched = {
            node_id
            for changed in pull_request.get("files") or []
            if (node_id := _node_file_id(changed["path"], tree_root))
        }
        for node_id in sorted({node_of_issue[n] for n in closed if n in node_of_issue} | touched):
            entry(node_id)["pull_requests"].append(
                {
                    "number": pull_request["number"],
                    "closes": [n for n in closed if node_of_issue.get(n) == node_id],
                    "touches_node_file": node_id in touched,
                }
            )
    return dict(sorted(works.items()))
