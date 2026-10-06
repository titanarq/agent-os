"""The sections of a slice that are plain text from a node's fields: the decisions in force, the
planning fields (state's neighbours: dependencies, hardenability), and the experiments and the
challenge. Split from `agent_os.product.tree.slicing`, which owns the cut itself and what a
verification looks like.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_os.product.tree.hardening import HardeningBlocker
from agent_os.product.tree.models import Experiment, Node

if TYPE_CHECKING:
    from agent_os.product.tree.slicing import Slice

UNDER_REVIEW_NOTE = "UNDER REVIEW -- still obeyed while it is challenged"
IN_FORCE_NOTE = "in force"


def section_heading(level: int, text: str) -> str:
    return f"{'#' * level} {text}"


def bullets(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items]


def yes_no(flag: bool) -> str:
    return "yes" if flag else "no"


def render_planning_bullets(node: Node, blockers: tuple[HardeningBlocker, ...]) -> list[str]:
    """The node's header bullets that say what stands between it and the rest of the work: what it
    depends on, and whether it may be hardened (and what says it may not)."""
    lines = []
    if node.depends_on:
        lines.append(f"- depends on: {', '.join(f'`{node_id}`' for node_id in node.depends_on)}")
    lines.append(f"- hardenable: {yes_no(not blockers)}")
    lines += [f"  - blocked by `{blocker.node_id}`: {blocker.reason}" for blocker in blockers]
    return lines


def _experiment_line(experiment: Experiment) -> str:
    label = experiment.kind
    if experiment.scope is not None:
        label += f" ({experiment.scope})"
    line = f"{experiment.date.isoformat()}, {label}, {experiment.outcome}: {experiment.question}"
    if experiment.finding is not None:
        line += f" -- {experiment.finding}"
    if experiment.default_answer is not None:
        line += f" (default answer: {experiment.default_answer})"
    return line


def render_experiments_and_challenge(node: Node, *, level: int) -> list[str]:
    lines: list[str] = []
    if node.experiments:
        lines += ["", section_heading(level, "Experiments"), ""]
        lines += bullets([_experiment_line(experiment) for experiment in node.experiments])
    if node.challenge is not None:
        explanation = f" -- {node.challenge.explanation}" if node.challenge.explanation else ""
        lines += [
            "",
            section_heading(level, "Challenge"),
            "",
            f"{node.challenge.reason}{explanation}",
        ]
    return lines


def render_decisions(cut: Slice, *, level: int) -> str:
    heading = section_heading(level, "Decisions in force")
    if not cut.decisions:
        return f"{heading}\n\nnone"
    blocks = []
    for entry in cut.decisions:
        decision = entry.decision
        standing = UNDER_REVIEW_NOTE if decision.state == "under-review" else IN_FORCE_NOTE
        block = [
            section_heading(level + 1, f"`{decision.id}`: {decision.title}"),
            "",
            f"- standing: {standing}",
            f"- decided: {decision.decided.isoformat()}",
            f"- binds this node through: `{entry.attached_to}`",
            "",
            decision.statement,
            "",
            "Premises:",
            *bullets(decision.premises),
            "",
            "Rejected alternatives:",
            *bullets(
                [
                    f"{alternative.option} -- {alternative.reason}"
                    f"{' (implied, not argued at approval)' if alternative.basis == 'implied' else ''}"
                    for alternative in decision.rejected_alternatives
                ]
            ),
            "",
            "Review triggers:",
            *bullets(decision.review_triggers),
            "",
            f"Friction entries logged against it: {len(decision.friction)}",
        ]
        blocks.append("\n".join(block))
    return "\n\n".join([heading, *blocks])
