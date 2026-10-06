"""Dispatch tickets from the nodes that are ready to be worked.

`compile` only RENDERS: it returns text, data and files and calls no `gh`, no network and no
backend. Creating the issues from what it renders is Phase 2's wiring, and keeping the two apart is
what lets this half be tested without a tracker and be run by anyone to see what a tree would
dispatch (`docs/adr/2026-10-04-the-product-tree-and-the-decision-ledger-are-markdown-files-with-a-doctor.md`).

A ticket has the shape of the repository's own dispatchable issues -- the seven sections of
`agent_os.lib.REQUIRED_SECTIONS` in order, then the `<!-- budget: <class> -->` line -- and
`validate_issue_body`, the one implementation of "is this a brief an agent could start from", is
asked about every body before it is returned, so a ticket the dispatcher would refuse is never
rendered. Its address is one more marker line, `<!-- node: <id> -->`: Phase 2 finds the node a
ticket came from, and the ticket a node already has, by that line alone.

Which nodes become tickets (the rule is one place, `_classify`):

- a goal is never a ticket, whether or not it carries a verification: that is its acceptance;
- a node past `pending` (improvised, hardened) is not dispatched by this step;
- a node with children is a container -- its use cases are the work -- and is skipped without
  comment, whether or not it has a verification: tests run top-down from the goals, so a
  container's verification is the acceptance of its subtree (it reaches every descendant's ticket
  as context, see `agent_os.product.tree.slicing`) and never a ticket of its own;
- every other pending node needs an executable verification -- a `command`; a criterion an agent
  judges is acceptance and not executable -- and a mechanism that can be resolved (written, or
  `pending` with no spike having found it infeasible). One that lacks either is an ESCALATION:
  reported, with its reason, and never turned into a ticket. A node's judged criteria are still
  rendered in its ticket's acceptance criteria, labelled as judged by an agent.
"""

from __future__ import annotations

import json
import pathlib
import re
from collections.abc import Sequence
from dataclasses import dataclass

from agent_os.issues import prefixed_title, type_labels
from agent_os.lib import AgentsConfig, validate_issue_body
from agent_os.product.tree.checks import check_tree
from agent_os.product.tree.loader import Defect, Tree
from agent_os.product.tree.models import MECHANISM_PENDING, Node
from agent_os.product.tree.slicing import (
    JUDGED_BY_AGENT_LABEL,
    Slice,
    assemble_slice,
    judged_criterion_line,
    render_ancestors,
    render_decisions,
    render_node,
)

NODE_MARKER_RE = re.compile(r"<!--\s*node:\s*([a-z0-9]+(?:-[a-z0-9]+)*)\s*-->")

MISSING_VERIFICATION = "missing-verification"
MECHANISM_UNRESOLVABLE = "mechanism-unresolvable"

TASK_TYPE = "task"


def parse_node_marker(body: str) -> str | None:
    """The id of the node a ticket body was compiled from, or None: the counterpart of
    `agent_os.lib.parse_budget_line` for the address line."""
    match = NODE_MARKER_RE.search(body or "")
    return match.group(1) if match else None


class CompileError(Exception):
    """`compile` cannot render honestly. `defects` are the doctor's lines when the tree is why."""

    def __init__(self, message: str, defects: tuple[Defect, ...] = ()) -> None:
        super().__init__(message)
        self.defects = defects


@dataclass(frozen=True)
class Ticket:
    node_id: str
    # The node's file, relative to the host's root when the tree sits under it.
    path: str
    title: str
    body: str
    labels: tuple[str, ...]
    budget_class: str


@dataclass(frozen=True)
class Escalation:
    node_id: str
    path: str
    code: str
    message: str


@dataclass(frozen=True)
class CompileResult:
    tickets: tuple[Ticket, ...]
    escalations: tuple[Escalation, ...]
    goals: int
    containers: int
    past_pending: int


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
    if not node.has_executable_verification:
        reasons.append(
            (
                MISSING_VERIFICATION,
                (
                    f"pending {node.type} with no executable `verification`: a node without one "
                    "escalates instead of dispatching -- write the command that proves it, or "
                    "ask the owner what does"
                ),
            )
        )
    infeasible = [spike for spike in node.spikes if spike.outcome == "infeasible"]
    if node.mechanism == MECHANISM_PENDING and infeasible:
        reasons.append(
            (
                MECHANISM_UNRESOLVABLE,
                (
                    "mechanism is `pending` and a spike found it infeasible "
                    f"({infeasible[0].question}: {infeasible[0].finding}); a mechanism has to be "
                    "found or the node revised before it can be dispatched"
                ),
            )
        )
    return reasons


def _acceptance_criteria(node: Node) -> list[str]:
    return [
        f"- {judged_criterion_line(check)}"
        if check.is_judged
        else f"- `{check.command}` exits 0" + (f": {check.expects}" if check.expects else "")
        for check in node.verification
    ]


def _stages(node: Node, node_file: str) -> list[str]:
    stages = []
    if node.mechanism == MECHANISM_PENDING:
        stages.append(
            f"- [ ] Resolve the solution mechanism of `{node.id}` (spike first if feasibility is "
            f"in doubt) and write it into `mechanism` of `{node_file}`; verified by the tree "
            "doctor passing"
        )
    judged = any(check.is_judged for check in node.verification)
    verified_by = (
        f"those commands, the criteria {JUDGED_BY_AGENT_LABEL} and the project's tests"
        if judged
        else "those commands and the project's tests"
    )
    stages.append(
        f"- [ ] Implement `{node.id}` until every acceptance criterion passes; verified by "
        f"{verified_by}"
    )
    return stages


def render_ticket_body(cut: Slice, *, budget_class: str, tree_root: str) -> str:
    node = cut.node
    node_file = f"{tree_root}/{cut.relative_path}"
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
        ("## Acceptance criteria", "\n".join(_acceptance_criteria(node))),
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
        ("## Dependencies", "none"),
        (
            "## Definition of done",
            (
                "- Every acceptance criterion passes.\n"
                f"- `{node_file}` is updated in the same pull request: `mechanism` when it was "
                f"`{MECHANISM_PENDING}`, `implementation`, and `state: hardened`; the tree "
                "doctor passes.\n"
                "- Tests and documentation as the project's AGENTS.md asks."
            ),
        ),
    ]
    body = "\n\n".join(f"{heading}\n{text}" for heading, text in sections)
    return f"{body}\n\n<!-- budget: {budget_class} -->\n<!-- node: {node.id} -->\n"


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
    tickets: list[Ticket] = []
    escalations: list[Escalation] = []
    skipped = {"goal": 0, "past-pending": 0, "container": 0}
    # Foundation nodes first: the shell does not go live until they are hardened, so they are what
    # a human reading the output wants to see before anything else.
    for node in sorted(tree.nodes.values(), key=lambda item: (not item.foundation, item.id)):
        verdict = _classify(node, node.id in parents)
        path = f"{tree_root}/{tree.paths[node.id].relative_to(tree.root).as_posix()}"
        if isinstance(verdict, str):
            skipped[verdict] += 1
            continue
        if verdict:
            escalations += [Escalation(node.id, path, code, message) for code, message in verdict]
            continue
        body = render_ticket_body(
            assemble_slice(tree, node.id), budget_class=budget_class, tree_root=tree_root
        )
        failures = validate_issue_body(body, task_classes=config.classes, open_issue_numbers=set())
        if failures:
            raise CompileError(
                f"the ticket rendered from {node.id!r} is not a dispatchable issue body: "
                + "; ".join(failures)
            )
        tickets.append(
            Ticket(
                node_id=node.id,
                path=path,
                title=prefixed_title(node.title, TASK_TYPE),
                body=body,
                labels=labels,
                budget_class=budget_class,
            )
        )
    return CompileResult(
        tickets=tuple(tickets),
        escalations=tuple(escalations),
        goals=skipped["goal"],
        containers=skipped["container"],
        past_pending=skipped["past-pending"],
    )


def _summary(result: CompileResult) -> dict[str, int]:
    return {
        "tickets": len(result.tickets),
        "escalations": len(result.escalations),
        "goals_skipped": result.goals,
        "containers_skipped": result.containers,
        "past_pending_skipped": result.past_pending,
    }


def render_compile_text(result: CompileResult) -> str:
    summary = _summary(result)
    lines = [
        (
            f"compiled {summary['tickets']} ticket(s), {summary['escalations']} escalation(s); "
            f"not dispatched by this step: {summary['goals_skipped']} goal(s), "
            f"{summary['containers_skipped']} container(s), "
            f"{summary['past_pending_skipped']} node(s) past pending"
        )
    ]
    for ticket in result.tickets:
        lines += [
            "",
            f"=== ticket: {ticket.node_id} ===",
            f"title: {ticket.title}",
            f"labels: {', '.join(ticket.labels)}",
            f"budget: {ticket.budget_class}",
            f"node: {ticket.path}",
            "---",
            ticket.body.rstrip("\n"),
        ]
    for escalation in result.escalations:
        lines += [
            "",
            f"=== escalation: {escalation.node_id} ===",
            f"{escalation.path}: {escalation.code}: {escalation.message}",
        ]
    return "\n".join(lines) + "\n"


def compile_as_data(result: CompileResult) -> dict:
    return {
        "summary": _summary(result),
        "tickets": [
            {
                "node": ticket.node_id,
                "path": ticket.path,
                "title": ticket.title,
                "labels": list(ticket.labels),
                "budget_class": ticket.budget_class,
                "body": ticket.body,
            }
            for ticket in result.tickets
        ],
        "escalations": [
            {
                "node": escalation.node_id,
                "path": escalation.path,
                "code": escalation.code,
                "message": escalation.message,
            }
            for escalation in result.escalations
        ],
    }


def render_compile_json(result: CompileResult) -> str:
    return json.dumps(compile_as_data(result), indent=2, ensure_ascii=False) + "\n"


def write_compile_files(result: CompileResult, out_dir: pathlib.Path) -> list[pathlib.Path]:
    """`<node id>.md` per ticket, holding exactly the issue body (what `issues.py create
    --body-file` takes), and `compile.json` holding everything else: titles, labels, escalations."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for ticket in result.tickets:
        path = out_dir / f"{ticket.node_id}.md"
        path.write_text(ticket.body, encoding="utf-8")
        written.append(path)
    index = out_dir / "compile.json"
    index.write_text(render_compile_json(result), encoding="utf-8")
    return [*written, index]
