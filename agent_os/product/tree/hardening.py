"""Whether a node may be hardened, and if not, what stands in the way.

Tests harden what use has already accepted (`docs/tree/dec-tests-harden-they-do-not-build.md`), so
two kinds of doubt keep a node schematic until they are settled: a `what` question still open
(`docs/tree/dec-a-doubt-of-how-is-settled-by-an-experiment.md`) and a challenge, which also blocks
whatever depends on the challenged node (`docs/tree/dec-a-challenge-is-flagged-early-and-the-owner-decides.md`).
This module only SAYS which node is blocked and why; what `compile` does with the answer is its
own concern.
"""

from __future__ import annotations

from dataclasses import dataclass

from agent_os.product.tree.loader import Tree
from agent_os.product.tree.reference_checks import nodes_reachable_through_dependencies

OPEN_WHAT_QUESTION = "open-what-question"
CHALLENGE_PREFIX = "challenge:"


@dataclass(frozen=True)
class HardeningBlocker:
    # The node that carries the doubt: the one asked about, or something it depends on.
    node_id: str
    # `open-what-question`, or `challenge:` followed by the challenge's reason.
    reason: str


def hardening_blockers(tree: Tree, node_id: str) -> list[HardeningBlocker]:
    """Every doubt that keeps `node_id` from hardening, its own first and then those of the nodes it
    depends on, directly or not, by id. Empty means the node is hardenable."""
    if node_id not in tree.nodes:
        raise KeyError(f"no node {node_id!r} in the tree")
    members = [node_id, *sorted(nodes_reachable_through_dependencies(tree, node_id) - {node_id})]
    blockers: list[HardeningBlocker] = []
    for member_id in members:
        member = tree.nodes.get(member_id)
        if member is None:
            continue
        if member.has_open_what_question:
            blockers.append(HardeningBlocker(member_id, OPEN_WHAT_QUESTION))
        if member.challenge is not None:
            blockers.append(HardeningBlocker(member_id, CHALLENGE_PREFIX + member.challenge.reason))
    return blockers


def is_hardenable(tree: Tree, node_id: str) -> bool:
    return not hardening_blockers(tree, node_id)
