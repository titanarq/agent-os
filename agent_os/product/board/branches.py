"""A branch of the tree as the board shows it.

A branch is a functional requirement under a goal. Its parts are its use cases; a requirement with
none is its own single part. The finishing reliability per branch
(`docs/tree/fr-challenges-are-found-early-and-reach-the-owner.md`) is left to Stage 2: it needs a
judgement of which use cases are hard to test that no field of the tree states yet.
"""

from __future__ import annotations

from dataclasses import dataclass

from agent_os.product.tree.loader import Tree
from agent_os.product.tree.models import Node

STATES_IN_PROGRESS_ORDER = ("pending", "improvised", "implemented", "hardened")
MARKER_PREFIX = "<!-- agent-os-board: "
MARKER_SUFFIX = " -->"


@dataclass(frozen=True)
class BranchPart:
    node_id: str
    title: str
    state: str


@dataclass(frozen=True)
class Branch:
    requirement_id: str
    title: str
    goal_id: str
    goal_title: str
    parts: list[BranchPart]
    open_what_questions: list[tuple[str, str, str | None]]  # (node id, question, default answer)
    challenges: list[tuple[str, str, str | None]]  # (node id, reason, explanation)
    depends_on: list[str]


def _members(tree: Tree, requirement: Node) -> list[Node]:
    children = sorted(
        (node for node in tree.nodes.values() if node.parent == requirement.id),
        key=lambda node: node.id,
    )
    return children or [requirement]


def _branch_of(tree: Tree, requirement: Node) -> Branch:
    goal = tree.nodes.get(requirement.parent or "")
    members = _members(tree, requirement)
    # The requirement's own doubts count even when its use cases carry the parts.
    carriers = [requirement, *[member for member in members if member is not requirement]]
    return Branch(
        requirement_id=requirement.id,
        title=requirement.title,
        goal_id=goal.id if goal else "",
        goal_title=goal.title if goal else "",
        parts=[BranchPart(member.id, member.title, member.state) for member in members],
        open_what_questions=[
            (carrier.id, experiment.question, experiment.default_answer)
            for carrier in carriers
            for experiment in carrier.experiments
            if experiment.is_open_what_question
        ],
        challenges=[
            (carrier.id, carrier.challenge.reason, carrier.challenge.explanation)
            for carrier in carriers
            if carrier.challenge is not None
        ],
        depends_on=list(requirement.depends_on),
    )


def build_branches(tree: Tree) -> list[Branch]:
    """One branch per functional requirement, in id order."""
    requirements = sorted(
        (node for node in tree.nodes.values() if node.type == "functional-requirement"),
        key=lambda node: node.id,
    )
    return [_branch_of(tree, requirement) for requirement in requirements]


def branch_progress_summary(branch: Branch) -> str:
    return " | ".join(
        f"{state} {sum(1 for part in branch.parts if part.state == state)}"
        for state in STATES_IN_PROGRESS_ORDER
    )


def branch_title(branch: Branch) -> str:
    return f"{branch.title} ({branch.requirement_id})"


def marker_for(requirement_id: str) -> str:
    return f"{MARKER_PREFIX}{requirement_id}{MARKER_SUFFIX}"


def requirement_id_in(body: str) -> str | None:
    """The requirement an item's body says it was generated from, or None for a hand-made item."""
    first_line = (body or "").splitlines()[0] if body else ""
    if first_line.startswith(MARKER_PREFIX) and first_line.endswith(MARKER_SUFFIX):
        return first_line[len(MARKER_PREFIX) : -len(MARKER_SUFFIX)]
    return None


def render_branch_body(branch: Branch) -> str:
    """Deterministic: the same branch renders the same text, so an unchanged tree is no change."""
    lines = [
        marker_for(branch.requirement_id),
        f"Goal: {branch.goal_title} ({branch.goal_id})",
        "",
        f"Progress: {branch_progress_summary(branch)}",
        "",
        "Parts:",
        *[f"- [{part.state}] {part.node_id}: {part.title}" for part in branch.parts],
    ]
    if branch.open_what_questions:
        lines += ["", "Open questions (what):"]
        for node_id, question, default_answer in branch.open_what_questions:
            lines.append(f"- {node_id}: {question} (default answer: {default_answer})")
    if branch.challenges:
        lines += ["", "Challenges:"]
        for node_id, reason, explanation in branch.challenges:
            lines.append(f"- {node_id}: {reason}" + (f" -- {explanation}" if explanation else ""))
    if branch.depends_on:
        lines += ["", "Depends on: " + ", ".join(branch.depends_on)]
    lines += [
        "",
        (
            "Generated from the product tree by `agent-os-tree board sync`; edit the tree's "
            "files, not this card. The owner's order is the Project's number field of that name."
        ),
    ]
    return "\n".join(lines)
