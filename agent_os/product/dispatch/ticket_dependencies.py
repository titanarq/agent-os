"""What a ticket waits for.

A node waits for its own `depends_on` and for those of every ancestor, because a use case is part of
its requirement and cannot start before the requirement can; a dependency on a container is a
dependency on the work under it, which is where the tickets are.

A v2 host's dispatch starts a ticket only once no open ticket belongs to a node it depends on
(`agent_os.product.dispatch.rules`), so it can only wait for a node that HAS a ticket. A node that
never will -- one already past `pending`, which a puntal or deployed code serves, or one that
escalates -- is no use in the `depends-on` marker, and it hides what that node waits for itself. The
ticket therefore takes that node's dependencies in its place (`ticket_dependencies`), as many levels
down as there are such nodes (`docs/tree/dec-dispatch-never-runs-two-tickets-on-the-same-code.md`).
"""

from __future__ import annotations

from collections.abc import Collection

from agent_os.product.tree.loader import Tree


def ancestor_ids(tree: Tree, node_id: str) -> list[str]:
    """The parent chain of a node, parent first. The doctor has refused a parent cycle by now."""
    chain: list[str] = []
    parent = tree.nodes[node_id].parent
    while parent is not None and parent in tree.nodes and parent not in chain:
        chain.append(parent)
        parent = tree.nodes[parent].parent
    return chain


def leaves_under(tree: Tree, node_id: str) -> list[str]:
    """`node_id` itself when it has no children, else the childless nodes below it."""
    children = [node.id for node in tree.nodes.values() if node.parent == node_id]
    if not children:
        return [node_id]
    return [leaf for child in sorted(children) for leaf in leaves_under(tree, child)]


def effective_dependencies(tree: Tree, node_id: str) -> tuple[str, ...]:
    """What a node waits for, whether or not those nodes have a ticket: its own `depends_on` and
    those of every ancestor, each as the childless nodes it stands for. Own dependencies come
    first, then the ancestors' from the nearest, each once; the node itself and its own ancestors
    are never among them."""
    chain = ancestor_ids(tree, node_id)
    declared = [*tree.nodes[node_id].depends_on]
    for ancestor_id in chain:
        declared += tree.nodes[ancestor_id].depends_on
    effective: list[str] = []
    for target in declared:
        for leaf in leaves_under(tree, target):
            if leaf != node_id and leaf not in chain and leaf not in effective:
                effective.append(leaf)
    return tuple(effective)


def is_foundation_work(tree: Tree, node_id: str) -> bool:
    """Whether the node itself is flagged `foundation`, which goes out ahead of the rest. A use case
    under a foundation requirement is not one by inheritance: whether it is indispensable is the
    expert's call, node by node, and it says so with the flag on that use case
    (`docs/tree/fr-a-usable-product-exists-early.md`)."""
    return tree.nodes[node_id].foundation


def ticket_dependencies(
    tree: Tree, node_id: str, nodes_with_a_ticket: Collection[str]
) -> tuple[str, ...]:
    """What the ticket of `node_id` waits for, as tickets: `effective_dependencies` where each node
    with no ticket is replaced, in its place, by what that node waits for. A node met twice is named
    once, and a loop through nodes without a ticket ends where it started."""
    visited = {node_id}

    def waited_for(dependencies: tuple[str, ...]) -> list[str]:
        tickets: list[str] = []
        for dependency in dependencies:
            if dependency in visited:
                continue
            visited.add(dependency)
            if dependency in nodes_with_a_ticket:
                tickets.append(dependency)
            else:
                tickets += waited_for(effective_dependencies(tree, dependency))
        return tickets

    return tuple(waited_for(effective_dependencies(tree, node_id)))
