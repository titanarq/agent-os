"""The slice of the tree a worker's brief carries: its node's chain and nothing else.

`agent_os.issues brief` appends it to the brief of a ticket that has a node address, in a v2 host.
The brief is the whole of what a worker reads (`prompts/worker.md`), so this is the one door by
which the tree reaches it -- the node, its ancestors with their acceptance, the decisions in force
-- and never the tree itself (`docs/tree/fr-drift-is-caught-early-and-costs-at-most-one-step.md`).
The slice is cut from the tree as it is at dispatch, so a ticket compiled before a node changed
still hands the worker the node as it is now.
"""

from __future__ import annotations

from agent_os import lib
from agent_os.cli import host_root
from agent_os.product.dispatch.markers import parse_node_marker
from agent_os.product.dispatch.rules import is_v2_host
from agent_os.product.tree.loader import load_tree, require_tree_root
from agent_os.product.tree.slicing import build_slice, render_slice_markdown


def brief_slice_section(issue_body: str | None) -> str:
    """The section to append to a brief, or "" when the host is not v2 or the issue has no
    address. A node the tree no longer has, or a tree that fails the doctor where the slice is
    cut, raises: a brief with a missing slice would send the worker to improvise the node."""
    node_id = parse_node_marker(issue_body or "")
    if node_id is None:
        return ""
    config = lib.load_agents_config(lib.DEFAULT_AGENTS_CONFIG)
    if not is_v2_host(config):
        return ""
    tree = load_tree(require_tree_root(host_root() / config.tree.root))
    cut = build_slice(tree, node_id)
    return (
        f"\n## Slice of node `{node_id}` (from `agent-os-tree context {node_id}`)\n\n"
        "This is everything the tree says about your node. The rest of the tree is deliberately "
        "not here: do not go reading it.\n\n" + render_slice_markdown(cut)
    )
