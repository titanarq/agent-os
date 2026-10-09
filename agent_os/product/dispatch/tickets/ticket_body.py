"""The body of a compiled ticket: the repository's seven sections in order, then the markers."""

from __future__ import annotations

from collections.abc import Sequence

from agent_os.product.dispatch.markers import render_marker_lines
from agent_os.product.dispatch.touched_code import touched_paths_of
from agent_os.product.tree.hardening import HardeningBlocker
from agent_os.product.tree.models import MECHANISM_PENDING, Node, Verification
from agent_os.product.tree.slicing import (
    JUDGED_BY_AGENT_LABEL,
    Slice,
    judged_criterion_line,
    render_ancestors,
    render_decisions,
    render_node,
)


def _own_criterion_line(check: Verification) -> str:
    if check.is_judged:
        return f"- {judged_criterion_line(check)}"
    return f"- `{check.command}` exits 0" + (f": {check.expects}" if check.expects else "")


def _inherited_criterion_line(node: Node, ancestor: Node, check: Verification) -> str:
    if check.is_judged:
        held = " ".join((check.judge or "").split())
    else:
        held = f"`{' '.join((check.command or '').split())}` exits 0" + (
            f": {check.expects}" if check.expects else ""
        )
    return f"- {JUDGED_BY_AGENT_LABEL}: with `{node.id}` built, `{ancestor.id}` still holds: {held}"


def _acceptance_criteria(node: Node, ancestors: Sequence[Node]) -> list[str]:
    """The node's own verification, as it is written. A node with none is accepted by what a judge
    can still check against: its description, and the acceptance each ancestor carries (nearest
    first, the goal's evaluators last), which a goal always has
    (`docs/tree/dec-top-down-acceptance-is-essential-even-when-judged.md`). Dispatch does not wait
    for a verification (`docs/tree/dec-tests-harden-they-do-not-build.md`), and the validator's rule
    for such a node -- judge it against its description -- is the first line."""
    if node.verification:
        return [_own_criterion_line(check) for check in node.verification]
    return [
        (
            f"- {JUDGED_BY_AGENT_LABEL}: `{node.id}` does what its description says "
            "(the Objective above)"
        ),
        *(
            _inherited_criterion_line(node, ancestor, check)
            for ancestor in ancestors
            for check in ancestor.verification
        ),
    ]


def _verified_by(node: Node) -> str:
    judged = any(check.is_judged for check in node.verification)
    if not node.has_executable_verification:
        return f"the criteria {JUDGED_BY_AGENT_LABEL} and then the owner's use"
    if judged:
        return f"those commands, the criteria {JUDGED_BY_AGENT_LABEL} and then the owner's use"
    return "those commands and then the owner's use"


def _stages(node: Node, node_file: str) -> list[str]:
    stages = []
    if node.mechanism == MECHANISM_PENDING:
        stages.append(
            f"- [ ] Resolve the solution mechanism of `{node.id}` (experiment first if feasibility is "
            f"in doubt) and write it into `mechanism` of `{node_file}`; verified by the tree "
            "doctor passing"
        )
    stages.append(
        f"- [ ] Implement `{node.id}` until every acceptance criterion passes; verified by "
        f"{_verified_by(node)}"
    )
    return stages


def _dependencies_section(depends_on: Sequence[str]) -> str:
    if not depends_on:
        return "none"
    listed = ", ".join(f"`{node_id}`" for node_id in depends_on)
    return (
        f"Depends on the nodes {listed}: this ticket starts only once the tickets of those nodes "
        "are closed."
    )


def _definition_of_done(node: Node, node_file: str, blockers: Sequence[HardeningBlocker]) -> str:
    lines = [
        "- Every acceptance criterion passes.",
        (
            f"- `{node_file}` is updated in the same pull request: `mechanism` when it was "
            f"`{MECHANISM_PENDING}`, `implementation` (the paths of the code built), and "
            "`state: implemented`; the tree doctor passes. The commit carries the `Node-Change` "
            "trailer."
        ),
        (
            "- No test is written for this node: tests harden what use has accepted, they do not "
            "build (`docs/tree/dec-tests-harden-they-do-not-build.md`), so the node is not "
            "marked `hardened` either. Its acceptance criteria are how it is verified; the tests "
            "the project already has must keep passing, and what the project's AGENTS.md asks of "
            "the tests of new code waits for the node's hardening."
        ),
    ]
    if blockers:
        reasons = "; ".join(f"`{blocker.node_id}`: {blocker.reason}" for blocker in blockers)
        lines.append(
            f"- The node cannot be hardened yet ({reasons}); this ticket does not wait for that."
        )
    lines.append("- Documentation as the project's AGENTS.md asks.")
    return "\n".join(lines)


def render_ticket_body(
    cut: Slice,
    *,
    budget_class: str,
    tree_root: str,
    blockers: Sequence[HardeningBlocker] = (),
    depends_on: Sequence[str] | None = None,
) -> str:
    """`depends_on` is what the ticket waits for when that is more than the node declares (the
    dependencies it inherits from its requirements); by default, the node's own."""
    node = cut.node
    waits_for = node.depends_on if depends_on is None else depends_on
    node_file = f"{tree_root}/{cut.relative_path}"
    touched_paths = touched_paths_of(node)
    context = "\n\n".join(
        [
            (
                f"Compiled from node `{node.id}` of the product tree under `{tree_root}`; its "
                f"file is `{node_file}`. Everything an agent needs about it is below, and the "
                "rest of the tree is deliberately absent."
            ),
            render_node(cut, level=3, with_description=False, with_verification=False),
            render_ancestors(cut, level=3),
            render_decisions(cut, level=3),
        ]
    )
    sections = [
        ("## Objective", f"Build the {node.type} `{node.id}`: {node.title}\n\n{node.description}"),
        ("## Acceptance criteria", "\n".join(_acceptance_criteria(node, cut.ancestors))),
        ("## Stages", "\n".join(_stages(node, node_file))),
        ("## Context", context),
        (
            "## Not included",
            (
                f"- Anything outside `{node.id}`: its siblings and its descendants have tickets "
                "of their own.\n"
                "- Re-deciding a decision listed under Context: obey it, and say in the pull "
                "request where it made the solution worse."
            ),
        ),
        ("## Dependencies", _dependencies_section(waits_for)),
        ("## Definition of done", _definition_of_done(node, node_file, blockers)),
    ]
    body = "\n\n".join(f"{heading}\n{text}" for heading, text in sections)
    markers = [
        f"<!-- budget: {budget_class} -->",
        *render_marker_lines(node.id, waits_for, touched_paths),
    ]
    return f"{body}\n\n" + "\n".join(markers) + "\n"
