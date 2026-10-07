"""When a v2 host's planner may start a ticket: the rules, over issue rows and nothing else.

A host is a **v2 host** when its `config/agents.yaml` sets `tree.dispatch_by_node: true`: a host says
so itself, because the example config documents `tree.root` with its default and a host that merely
has a tree directory is not yet one whose work comes from it
(`docs/adr/2026-10-07-a-v2-host-dispatches-by-node-address-dependencies-first-and-never-on-the-same-code.md`).
In a v2 host a ticket may start only when

- it carries a node address (`<!-- node: <id> -->`): work that answers to no node answers to no goal;
- no open issue is the ticket of a node it depends on: dependencies go first;
- it touches no code that a running ticket touches: never two tickets on the same code.

Every function takes plain rows (`{"number": int, "body": str}`) so the guard's scan, the driver's
start gate and the tests all ask the same thing. Nothing here calls `gh`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from agent_os import lib
from agent_os.lib import AgentsConfig
from agent_os.product.dispatch.markers import (
    parse_dependency_markers,
    parse_node_marker,
    parse_touched_paths,
)
from agent_os.product.dispatch.touched_code import overlapping_paths

IssueRow = Mapping[str, object]


def is_v2_host(config: AgentsConfig) -> bool:
    return config.tree.dispatch_by_node


def _body(row: IssueRow) -> str:
    return str(row.get("body") or "")


def tree_dispatch_refusals(
    row: IssueRow, open_rows: Iterable[IssueRow], running_rows: Iterable[IssueRow] = ()
) -> list[str]:
    """Why `row` may not start in a v2 host, one sentence each; empty means it may."""
    body = _body(row)
    node_id = parse_node_marker(body)
    if node_id is None:
        return [
            "it carries no node address (`<!-- node: <id> -->`): in a v2 host a ticket answers to a node"
        ]
    refusals = []
    open_nodes = {
        parse_node_marker(_body(other)): other["number"]
        for other in open_rows
        if other["number"] != row["number"]
    }
    for dependency in parse_dependency_markers(body):
        if dependency in open_nodes:
            refusals.append(
                f"it depends on node `{dependency}`, whose ticket #{open_nodes[dependency]} is still open"
            )
    touched = parse_touched_paths(body)
    for running in running_rows:
        shared = overlapping_paths(touched, parse_touched_paths(_body(running)))
        if shared:
            refusals.append(
                f"it touches {', '.join(shared)}, which running ticket #{running['number']} touches too"
            )
    return refusals


def rows_the_tree_rules_allow(
    ready_rows: Sequence[IssueRow], open_rows: Sequence[IssueRow], config: AgentsConfig
) -> list[IssueRow]:
    """`ready_rows` as they are in a host that is not v2; in a v2 host, those with an address and
    no open dependency. Collisions are not decided here: what is running is the start gate's to ask."""
    if not is_v2_host(config):
        return list(ready_rows)
    return [row for row in ready_rows if not tree_dispatch_refusals(row, open_rows)]


def rows_the_tree_rules_allow_here(
    ready_rows: Sequence[IssueRow], open_rows: Sequence[IssueRow]
) -> list[IssueRow]:
    """`rows_the_tree_rules_allow` under this host's own `config/agents.yaml`."""
    return rows_the_tree_rules_allow(
        ready_rows, open_rows, lib.load_agents_config(lib.DEFAULT_AGENTS_CONFIG)
    )
