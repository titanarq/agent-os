"""The slice of one node: what an agent needs to work on it, and nothing else.

Cost and quality degrade with the context of a call, not with the number of calls, so the unit an
agent is handed is never the tree. A slice is the node itself, its ancestors up to the goal, and
the decisions in force on that chain -- and by construction nothing of its siblings, its
descendants or any decision that does not bind it. Its size is bounded by the length of one chain
of ancestors, however large the tree grows (`tests/product/tree/test_tree_slice.py` pins that).

Each ancestor brings its verification too, labelled as the acceptance the node's work serves and
must not break: tests run top-down from the goals, so what a goal or a requirement is verified by
is what keeps the work below it from drifting, and the agent working on a use case is told which
evaluators stand above it. It is still the chain only -- an ancestor's verification, never a
sibling's or a descendant's. A verification is a command or a criterion an agent judges; a judged
one is rendered, for the node and for every ancestor, labelled as judged by an agent.

A decision that is `under-review` is in the slice and labelled as such: it is still obeyed while it
is challenged. A superseded decision is never in a slice; a node still pointing at one is a defect
the slice refuses to paper over.

The output is deterministic: the same tree gives the same bytes, whatever order the files were
written or listed in, so a brief built from a slice is diffable and cacheable.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from agent_os.product.tree.checks import check_tree
from agent_os.product.tree.hardening import HardeningBlocker, hardening_blockers
from agent_os.product.tree.loader import Defect, Tree
from agent_os.product.tree.models import MECHANISM_PENDING, Decision, Node, Verification
from agent_os.product.tree.slicing_fields import (
    ANCESTOR_ACCEPTANCE_NOTE,
    MECHANISM_PENDING_NOTE,
    ancestor_findings,
    bullets,
    render_ancestor_findings,
    render_decisions,
    render_experiments_and_challenge,
    render_planning_bullets,
    section_heading,
    yes_no,
)

# What marks a criterion as one an agent judges rather than a command that is run. One string for
# the Markdown slice, the JSON slice and the ticket's acceptance criteria, so they cannot drift.
JUDGED_BY_AGENT_LABEL = "judged by an agent"


class SliceError(Exception):
    """The slice cannot be cut honestly. `defects` are the doctor's own lines about the files it
    would have been made of, when that is why."""

    def __init__(self, message: str, defects: tuple[Defect, ...] = ()) -> None:
        super().__init__(message)
        self.defects = defects


@dataclass(frozen=True)
class SliceDecision:
    decision: Decision
    # The node or ancestor whose `decisions` pointer brings it into the slice: the nearest one,
    # when several do.
    attached_to: str


@dataclass(frozen=True)
class Slice:
    node: Node
    # The node's file relative to the tree root, so the slice reads the same on every machine.
    relative_path: str
    # Parent first, goal last.
    ancestors: tuple[Node, ...]
    decisions: tuple[SliceDecision, ...]
    # What keeps the node from hardening (`agent_os.product.tree.hardening`), empty when nothing.
    hardening_blockers: tuple[HardeningBlocker, ...] = ()

    @property
    def chain(self) -> tuple[Node, ...]:
        return (self.node, *self.ancestors)


def assemble_slice(tree: Tree, node_id: str) -> Slice:
    """The slice of `node_id`, assuming nothing about the rest of the tree beyond what the walk
    itself needs to terminate. `build_slice` is the one that also asks the doctor."""
    node = tree.nodes.get(node_id)
    if node is None:
        if node_id in tree.decisions:
            raise SliceError(f"{node_id!r} is a decision, not a node; a slice is cut around a node")
        if node_id in tree.unusable_ids:
            raise SliceError(
                f"node {node_id!r} cannot be loaded; `agent-os-tree validate` says why"
            )
        raise SliceError(f"no node {node_id!r} under {tree.root}")
    ancestors: list[Node] = []
    seen = {node.id}
    current = node
    while current.parent is not None:
        parent = tree.nodes.get(current.parent)
        if parent is None:
            raise SliceError(
                f"{current.id!r} has parent {current.parent!r}, which is not a usable node "
                "(dangling-parent; `agent-os-tree validate` says more)"
            )
        if parent.id in seen:
            raise SliceError(
                f"the parent chain of {node_id!r} loops at {parent.id!r} (parent-cycle)"
            )
        ancestors.append(parent)
        seen.add(parent.id)
        current = parent
    decisions: list[SliceDecision] = []
    taken: set[str] = set()
    for member in (node, *ancestors):
        for decision_id in sorted(set(member.decisions)):
            if decision_id in taken:
                continue
            decision = tree.decisions.get(decision_id)
            if decision is None or decision.state == "superseded":
                raise SliceError(
                    f"{member.id!r} points at decision {decision_id!r}, which is not a decision "
                    "in force (dangling-decision or superseded-decision-in-use)"
                )
            taken.add(decision_id)
            decisions.append(SliceDecision(decision=decision, attached_to=member.id))
    return Slice(
        node=node,
        relative_path=tree.paths[node.id].relative_to(tree.root).as_posix(),
        ancestors=tuple(ancestors),
        decisions=tuple(decisions),
        hardening_blockers=tuple(hardening_blockers(tree, node.id)),
    )


def build_slice(tree: Tree, node_id: str) -> Slice:
    """The slice of `node_id`, or a `SliceError` when any file it is made of is defective.

    The doctor is the single authority on "is this file sound", so the slice asks it rather than
    carrying a second copy of the rules, and looks only at the files it is made of: a defect in
    another branch of the tree never stops an agent from getting its own slice."""
    cut = assemble_slice(tree, node_id)
    files = {tree.paths[member.id] for member in cut.chain}
    files |= {tree.paths[entry.decision.id] for entry in cut.decisions}
    own_defects = tuple(defect for defect in check_tree(tree) if defect.path in files)
    if own_defects:
        raise SliceError(
            f"the slice of {node_id!r} is made of files that fail the doctor", own_defects
        )
    return cut


def judged_criterion_line(check: Verification) -> str:
    """`judged by an agent: <criterion>`, on ONE line. The criterion is a paragraph, and every
    consumer of this line (a slice read by an agent, a ticket body `validate_issue_body` reads line
    by line) is safer when a line of it cannot start with `##` or `Blocked by`, so its whitespace
    is collapsed; the words are not touched."""
    return f"{JUDGED_BY_AGENT_LABEL}: {' '.join((check.judge or '').split())}"


def _verification_bullets(node: Node) -> list[str]:
    return bullets(
        [
            judged_criterion_line(check)
            if check.is_judged
            else f"`{check.command}`" + (f" -- {check.expects}" if check.expects else "")
            for check in node.verification
        ]
    )


def verification_as_data(check: Verification) -> dict:
    """One entry of a `verification` list for `--json`: its `kind` first, so a reader branches on
    it, and a judged one carries the same label the Markdown slice prints."""
    if check.is_judged:
        return {"kind": "judge", "judge": check.judge, "label": JUDGED_BY_AGENT_LABEL}
    return {"kind": "command", "command": check.command, "expects": check.expects}


def render_node(
    cut: Slice, *, level: int, with_description: bool = True, with_verification: bool = True
) -> str:
    node = cut.node
    lines = [
        section_heading(level, f"Node `{node.id}`"),
        "",
        f"- type: {node.type}",
        f"- title: {node.title}",
        f"- state: {node.state}",
        *render_planning_bullets(node, cut.hardening_blockers),
        f"- foundation: {yes_no(node.foundation)}",
        f"- parent: {f'`{node.parent}`' if node.parent else 'none (a goal is the root)'}",
        f"- file: `{cut.relative_path}` (relative to the tree root)",
    ]
    if with_description:
        lines += ["", section_heading(level + 1, "Description"), "", node.description]
    if node.mechanism is not None:
        text = MECHANISM_PENDING_NOTE if node.mechanism == MECHANISM_PENDING else node.mechanism
        lines += ["", section_heading(level + 1, "Mechanism"), "", text]
    if node.implementation is not None:
        lines += ["", section_heading(level + 1, "Implementation"), "", node.implementation]
    # A goal's section is its evaluators, which the doctor requires; for any other node it may be
    # empty, and says so.
    if with_verification:
        shown = _verification_bullets(node)
        lines += ["", section_heading(level + 1, "Verification"), "", *(shown or ["none"])]
    lines += render_experiments_and_challenge(node, level=level + 1)
    lines += ["", section_heading(level + 1, "Sources"), "", *bullets(node.sources)]
    return "\n".join(lines)


def render_ancestors(cut: Slice, *, level: int) -> str:
    heading = section_heading(level, "Ancestors")
    if not cut.ancestors:
        return f"{heading}\n\nnone"
    blocks = []
    for ancestor in cut.ancestors:
        block = [
            section_heading(level + 1, f"`{ancestor.id}` ({ancestor.type}): {ancestor.title}"),
            "",
            ancestor.description,
            "",
            "Sources:",
            *bullets(ancestor.sources),
        ]
        if ancestor.verification:
            block += ["", ANCESTOR_ACCEPTANCE_NOTE, *_verification_bullets(ancestor)]
        block += render_ancestor_findings(ancestor)
        blocks.append("\n".join(block))
    return "\n\n".join([heading, *blocks])


def render_slice_markdown(cut: Slice) -> str:
    """The slice as a Markdown brief: the node, its ancestors, the decisions in force."""
    parts = [
        section_heading(1, f"Slice of `{cut.node.id}`"),
        render_node(cut, level=2),
        render_ancestors(cut, level=2),
        render_decisions(cut, level=2),
    ]
    return "\n\n".join(parts) + "\n"


def slice_as_data(cut: Slice) -> dict:
    """The slice as plain data, for `--json` and for the callers that would rather not parse
    Markdown."""
    return {
        "node": {
            **cut.node.model_dump(mode="json"),
            "verification": [verification_as_data(check) for check in cut.node.verification],
            "file": cut.relative_path,
            "hardenable": not cut.hardening_blockers,
            "hardening_blockers": [asdict(blocker) for blocker in cut.hardening_blockers],
        },
        "ancestors": [
            {
                "id": ancestor.id,
                "type": ancestor.type,
                "title": ancestor.title,
                "description": ancestor.description,
                "sources": ancestor.sources,
                "verification": [verification_as_data(check) for check in ancestor.verification],
                "experiments": ancestor_findings(ancestor),
            }
            for ancestor in cut.ancestors
        ],
        "decisions": [
            {
                "id": entry.decision.id,
                "title": entry.decision.title,
                "state": entry.decision.state,
                "attached_to": entry.attached_to,
                **entry.decision.model_dump(
                    mode="json",
                    include={
                        "decided",
                        "statement",
                        "premises",
                        "rejected_alternatives",
                        "review_triggers",
                    },
                ),
                "friction_count": len(entry.decision.friction),
            }
            for entry in cut.decisions
        ],
    }


def render_slice_json(cut: Slice) -> str:
    return json.dumps(slice_as_data(cut), indent=2, ensure_ascii=False) + "\n"
