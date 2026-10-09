"""Dispatch tickets from the nodes that are ready to be worked.

`compile` only RENDERS: it returns text, data and files and calls no `gh`, no network and no
backend. Creating the issues from what it renders is Phase 2's wiring, and keeping the two apart is
what lets this half be tested without a tracker and be run by anyone to see what a tree would
dispatch (`docs/adr/2026-10-04-the-product-tree-and-the-decision-ledger-are-markdown-files-with-a-doctor.md`).

A ticket has the shape of the repository's own dispatchable issues -- the seven sections of
`agent_os.lib.REQUIRED_SECTIONS` in order, then the `<!-- budget: <class> -->` line -- and
`validate_issue_body`, the one implementation of "is this a brief an agent could start from", is
asked about every body before it is returned, so a ticket the dispatcher would refuse is never
rendered. Three more marker lines say what the ticket is (`agent_os.product.dispatch.markers`): its
node address, the nodes it depends on and the code it touches. Phase 2 finds the node a ticket came
from, and a v2 host's planner decides from them what may start. Tickets come ordered by their
dependencies, a dependency before whatever depends on it, and a ticket depends only on nodes that
have a ticket: a dependency that never gets one is replaced by what it waits for
(`agent_os.product.dispatch.tickets.ticket_dependencies`).

Which nodes become tickets (the rule is one place, `_classify`):

- a goal is never a ticket, whether or not it carries a verification: that is its acceptance;
- a node past `pending` (improvised, implemented, hardened) is not dispatched by this step;
- a node with children is a container -- its use cases are the work -- and is skipped without
  comment, whether or not it has a verification: tests run top-down from the goals, so a
  container's verification is the acceptance of its subtree (it reaches every descendant's ticket
  as context, see `agent_os.product.tree.slicing`) and never a ticket of its own;
- every other pending node is dispatched, with a command, a judged criterion or neither: tests
  harden, they do not build (`docs/tree/dec-tests-harden-they-do-not-build.md`), and the essential
  top-down acceptance holds even when an agent judges it. The one thing that stops it is a
  mechanism that cannot be resolved (`pending`, with an experiment having found it infeasible):
  an ESCALATION, reported with its reason and never turned into a ticket.

A ticket builds, it never hardens: its definition of done leaves the node `implemented`, and says
so, with the doubts that keep the node from hardening (`agent_os.product.tree.hardening`), when it
has any.
"""

from __future__ import annotations

from collections.abc import Sequence

from agent_os.issues import prefixed_title, type_labels
from agent_os.lib import AgentsConfig, validate_issue_body
from agent_os.product.dispatch.markers import parse_node_marker
from agent_os.product.dispatch.tickets.compile_output import (
    compile_as_data,
    render_compile_json,
    render_compile_text,
    write_compile_files,
)
from agent_os.product.dispatch.tickets.results import CompileResult, Escalation, Ticket
from agent_os.product.dispatch.tickets.ticket_body import render_ticket_body
from agent_os.product.dispatch.tickets.ticket_dependencies import (
    effective_dependencies,
    is_foundation_work,
    ticket_dependencies,
)
from agent_os.product.dispatch.touched_code import touched_paths_of
from agent_os.product.tree.checks import check_tree
from agent_os.product.tree.hardening import hardening_blockers
from agent_os.product.tree.loader import Defect, Tree
from agent_os.product.tree.models import MECHANISM_PENDING, Node
from agent_os.product.tree.slicing import assemble_slice

__all__ = [
    "MECHANISM_UNRESOLVABLE",
    "CompileError",
    "CompileResult",
    "Escalation",
    "Ticket",
    "compile_as_data",
    "compile_tree",
    "parse_node_marker",
    "render_compile_json",
    "render_compile_text",
    "render_ticket_body",
    "write_compile_files",
]

MECHANISM_UNRESOLVABLE = "mechanism-unresolvable"

TASK_TYPE = "task"


class CompileError(Exception):
    """`compile` cannot render honestly. `defects` are the doctor's lines when the tree is why."""

    def __init__(self, message: str, defects: tuple[Defect, ...] = ()) -> None:
        super().__init__(message)
        self.defects = defects


def _classify(node: Node, has_children: bool) -> str | list[tuple[str, str]]:
    """`goal`, `past-pending`, `container` for what is skipped; a list of `(code, message)` reasons
    for a node that must escalate; an empty list for a dispatchable one."""
    if node.type == "goal":
        return "goal"
    if node.state != "pending":
        return "past-pending"
    if has_children:
        return "container"
    reasons: list[tuple[str, str]] = []
    infeasible = [e for e in node.experiments if e.outcome == "infeasible"]
    if node.mechanism == MECHANISM_PENDING and infeasible:
        reasons.append(
            (
                MECHANISM_UNRESOLVABLE,
                (
                    "mechanism is `pending` and an experiment found it infeasible "
                    f"({infeasible[0].question}: {infeasible[0].finding}); a mechanism has to be "
                    "found or the node revised before it can be dispatched"
                ),
            )
        )
    return reasons


def _require_worker_class(config: AgentsConfig, budget_class: str) -> None:
    if not budget_class:
        raise CompileError(
            "no budget class for the tickets: pass --budget-class, or set tree.ticket_budget_class "
            "in config/agents.yaml"
        )
    task_class = config.classes.get(budget_class)
    if task_class is None or task_class.role != "worker":
        workers = sorted(name for name, task in config.classes.items() if task.role == "worker")
        raise CompileError(f"budget class {budget_class!r} is not a worker class (have {workers})")


def _labels(config: AgentsConfig, extra_labels: Sequence[str]) -> tuple[str, ...]:
    available = type_labels(config.project)
    if TASK_TYPE not in available:
        raise CompileError(
            f"project.labels.types has no {TASK_TYPE!r}, so a ticket has no type label to carry"
        )
    return tuple(dict.fromkeys([available[TASK_TYPE], *config.tree.ticket_labels, *extra_labels]))


def _in_dependency_order(tree: Tree, node_ids: Sequence[str]) -> list[str]:
    """`node_ids` with every node after the nodes it depends on, directly, through others or
    through its ancestors (`effective_dependencies`); foundations first and then by id among the
    nodes that are free to go. Dependencies that loop only once inherited are refused."""
    wanted = set(node_ids)
    waiting_for: dict[str, set[str]] = {}
    for node_id in node_ids:
        # Through a node that is no ticket (improvised, say) the order still holds, so the walk
        # follows every edge and keeps only the tickets at the end.
        reached: set[str] = set()
        pending = [node_id]
        while pending:
            for dependency in effective_dependencies(tree, pending.pop()):
                if dependency not in reached:
                    reached.add(dependency)
                    pending.append(dependency)
        if node_id in reached:
            raise CompileError(
                f"the dependencies of {node_id!r}, its requirements' included, loop back to it"
            )
        waiting_for[node_id] = reached & wanted
    ordered: list[str] = []
    while waiting_for:
        free = [node_id for node_id, blockers in waiting_for.items() if not blockers]
        chosen = min(free, key=lambda node_id: (not is_foundation_work(tree, node_id), node_id))
        ordered.append(chosen)
        del waiting_for[chosen]
        for blockers in waiting_for.values():
            blockers.discard(chosen)
    return ordered


def _render_ticket(
    tree: Tree,
    node: Node,
    config: AgentsConfig,
    *,
    budget_class: str,
    tree_root: str,
    depends_on: Sequence[str],
) -> tuple[str, tuple[str, ...]]:
    body = render_ticket_body(
        assemble_slice(tree, node.id),
        budget_class=budget_class,
        tree_root=tree_root,
        blockers=hardening_blockers(tree, node.id),
        depends_on=depends_on,
    )
    failures = validate_issue_body(body, task_classes=config.classes, open_issue_numbers=set())
    if failures:
        raise CompileError(
            f"the ticket rendered from {node.id!r} is not a dispatchable issue body: "
            + "; ".join(failures)
        )
    return body, touched_paths_of(node)


def compile_tree(
    tree: Tree,
    config: AgentsConfig,
    *,
    budget_class: str,
    tree_root: str,
    extra_labels: Sequence[str] = (),
) -> CompileResult:
    """The tickets and escalations of a tree. Refuses a tree the doctor finds anything in: a ticket
    is a durable record in an external tracker, and one rendered from a broken tree would outlive
    the fix. `tree_root` is how the root is named inside a ticket (relative to the host's root)."""
    defects = tuple(check_tree(tree))
    if defects:
        raise CompileError("the tree fails the doctor, so nothing is compiled from it", defects)
    _require_worker_class(config, budget_class)
    labels = _labels(config, extra_labels)
    parents = {node.parent for node in tree.nodes.values() if node.parent is not None}
    dispatchable: list[str] = []
    escalations: list[Escalation] = []
    skipped = {"goal": 0, "past-pending": 0, "container": 0}
    for node in sorted(tree.nodes.values(), key=lambda item: item.id):
        verdict = _classify(node, node.id in parents)
        path = f"{tree_root}/{tree.paths[node.id].relative_to(tree.root).as_posix()}"
        if isinstance(verdict, str):
            skipped[verdict] += 1
        elif verdict:
            escalations += [Escalation(node.id, path, code, message) for code, message in verdict]
        else:
            dispatchable.append(node.id)
    nodes_with_a_ticket = set(dispatchable)
    tickets: list[Ticket] = []
    for node_id in _in_dependency_order(tree, dispatchable):
        node = tree.nodes[node_id]
        path = f"{tree_root}/{tree.paths[node_id].relative_to(tree.root).as_posix()}"
        depends_on = ticket_dependencies(tree, node_id, nodes_with_a_ticket)
        body, touched_paths = _render_ticket(
            tree,
            node,
            config,
            budget_class=budget_class,
            tree_root=tree_root,
            depends_on=depends_on,
        )
        tickets.append(
            Ticket(
                node_id=node_id,
                path=path,
                title=prefixed_title(node.title, TASK_TYPE),
                body=body,
                labels=labels,
                budget_class=budget_class,
                depends_on=depends_on,
                touched_paths=touched_paths,
            )
        )
    return CompileResult(
        tickets=tuple(tickets),
        escalations=tuple(escalations),
        goals=skipped["goal"],
        containers=skipped["container"],
        past_pending=skipped["past-pending"],
    )
