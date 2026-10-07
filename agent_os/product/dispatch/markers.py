"""The marker lines at the end of a compiled ticket, written and read back.

    <!-- budget: <class> -->            (written by compile, read by agent_os.lib)
    <!-- node: <node id> -->            the address: which node the ticket came from
    <!-- depends-on: <id>, <id> -->     the nodes whose tickets must be closed first (when any)
    <!-- touches: <path>, <path> -->    the code the node is known to touch (when any)

A marker is a comment, so it never shows in the rendered issue, and one line each, so a person or a
`grep` finds it. The reader and the writer live in this one file.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

IDENTIFIER = r"[a-z0-9]+(?:-[a-z0-9]+)*"
NODE_MARKER_RE = re.compile(rf"<!--\s*node:\s*({IDENTIFIER})\s*-->")
DEPENDS_ON_MARKER_RE = re.compile(r"<!--\s*depends-on:\s*(.*?)\s*-->")
TOUCHES_MARKER_RE = re.compile(r"<!--\s*touches:\s*(.*?)\s*-->")


def _split_list(text: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in text.split(",") if item.strip())


def parse_node_marker(body: str) -> str | None:
    """The id of the node a ticket body was compiled from, or None: the counterpart of
    `agent_os.lib.parse_budget_line` for the address line."""
    match = NODE_MARKER_RE.search(body or "")
    return match.group(1) if match else None


def parse_dependency_markers(body: str) -> tuple[str, ...]:
    """The node ids the ticket waits for; empty when the line is absent."""
    match = DEPENDS_ON_MARKER_RE.search(body or "")
    return _split_list(match.group(1)) if match else ()


def parse_touched_paths(body: str) -> tuple[str, ...]:
    """The paths the ticket's node is known to touch; empty when the line is absent."""
    match = TOUCHES_MARKER_RE.search(body or "")
    return _split_list(match.group(1)) if match else ()


def render_marker_lines(
    node_id: str, depends_on: Sequence[str], touched_paths: Sequence[str]
) -> list[str]:
    lines = [f"<!-- node: {node_id} -->"]
    if depends_on:
        lines.append(f"<!-- depends-on: {', '.join(depends_on)} -->")
    if touched_paths:
        lines.append(f"<!-- touches: {', '.join(touched_paths)} -->")
    return lines
