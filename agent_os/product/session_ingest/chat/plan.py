"""What ingesting one closed chat session would do, decided without changing anything.

The owner's words are split by the interpreter into items (`docs/FEEDBACK_INTERPRETER.md`); each item
points at the messages it came from (`from_messages`). From there:

- a `change` that is not withdrawn becomes one issue, directly;
- a `decision` is NOT launched: it is kept for the owner to confirm when the next session opens;
- a `question_of_what` is kept the same way, as an open question;
- a withdrawn item is nothing;
- a case whose last state is `perfect` is recorded on its node as the owner's acceptance;
- the owner's text that no item covers (a session closed before the interpreter was connected, or a
  message the interpreter could not read) is never dropped: by the last state of its case, `needs_work`
  returns as rework and `ok_with_improvements` as a change, each quoting the thread of the case, and a
  comment on no case as one general change that says no interpreter read it.

A step already done (the answer written, the acceptance recorded, the issue opened) says so and is
not repeated; a step that cannot be done (a node the tree lacks) is a problem, never dropped.
"""

from __future__ import annotations

import pathlib
from collections.abc import Callable
from dataclasses import dataclass, field

from agent_os.product.session_ingest.chat.model import ChatSession, Comment, Item
from agent_os.product.session_ingest.chat.ticket import TicketSubject, change_key
from agent_os.product.session_ingest.feedback_summary import ActionVerdicts, summarize_verdicts
from agent_os.product.session_ingest.plan import (
    AcceptanceStep,
    AnswerStep,
    acceptance_step_for,
    answer_step_for,
)
from agent_os.product.session_ingest.rework_ticket import rework_key
from agent_os.product.tree.loader import Tree

# `<!-- key: -->` -> the number of the issue already opened for it, or None.
IssueLookup = Callable[[str], int | None]


@dataclass(frozen=True)
class IssueStep:
    """`origin` is why the issue exists: `item`, `rework`, `case change` or `general`."""

    origin: str
    subject: TicketSubject
    existing_issue: int | None


@dataclass
class ChatSessionPlan:
    session: ChatSession
    answers: list[AnswerStep] = field(default_factory=list)
    acceptances: list[AcceptanceStep] = field(default_factory=list)
    issues: list[IssueStep] = field(default_factory=list)
    kept_for_next_session: list[Item] = field(default_factory=list)
    withdrawn: list[Item] = field(default_factory=list)
    no_change_named: list[str] = field(default_factory=list)
    not_tried: list[str] = field(default_factory=list)
    verdicts: list[ActionVerdicts] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def _thread_text(session: ChatSession, positions: list[int]) -> str:
    lines = []
    for position in positions:
        comment = session.comments[position]
        details = ", ".join(d for d in (comment.state, comment.page) if d)
        suffix = f" ({details})" if details else ""
        lines.append(f"[{position}] {comment.role}{suffix}: {comment.text or '(no text)'}")
    return "\n".join(lines)


def _one_safe_line(text: str) -> str:
    """The interpreter's words are a model's output: one line, with no comment delimiter, so that
    they can neither open a section of the ticket nor forge a marker line."""
    return " ".join(text.split()).replace("<!--", "&lt;!--").replace("-->", "--&gt;")


def _item_step(plan: ChatSessionPlan, tree: Tree, item: Item, lookup: IssueLookup) -> None:
    if item.node is not None and item.node not in tree.nodes:
        plan.problems.append(
            f"{item.id}: no such node {item.node!r}, its change cannot be launched"
        )
        return
    where = f" (page {item.page})" if item.page else ""
    summary = _one_safe_line(item.summary)
    key = change_key(plan.session.id, f"item.{item.id}")
    subject = TicketSubject(
        key=key,
        title=f"{summary} (test session {plan.session.id}, {item.id})",
        summary=summary,
        objective=(
            f"The owner asked for this in test session `{plan.session.id}`{where}, as the "
            f"interpreter of the feedback read it: {summary}"
        ),
        messages=_thread_text(plan.session, list(item.from_messages)),
        node_id=item.node,
        is_rework=False,
    )
    plan.issues.append(IssueStep("item", subject, lookup(key)))


def _case_subject(session: ChatSession, node: str, kind: str, thread: list[int]) -> TicketSubject:
    rework = kind == "rework"
    verdict = "needs work" if rework else "ok with improvements"
    objective = (
        f"The owner gave `{node}` the state `{verdict}` in test session `{session.id}`, and no "
        "interpreter read what they wrote: the whole thread of the case follows. "
        + ("Make it do what the owner expected." if rework else "Make the changes the text names.")
    )
    title = (
        f"Rework `{node}`: needs work in test session {session.id}"
        if rework
        else f"Improve `{node}`: ok with improvements in test session {session.id}"
    )
    return TicketSubject(
        key=rework_key(session.id, node) if rework else change_key(session.id, f"case.{node}"),
        title=title,
        summary=title,
        objective=objective,
        messages=_thread_text(session, thread),
        node_id=node,
        is_rework=rework,
    )


def _plan_case(plan: ChatSessionPlan, tree: Tree, node: str, covered: set[int], lookup) -> None:
    session = plan.session
    thread = [i for i, comment in enumerate(session.comments) if comment.case == node]
    verdicts = {case.node: case.verdict for case in session.cases}
    last_state = next(
        (session.comments[i].state for i in reversed(thread) if session.comments[i].state), None
    )
    verdict = verdicts.get(node) or last_state or "not_tried"
    uncovered_text = [
        i for i in thread if _is_uncovered_owner_text(session.comments[i], i, covered)
    ]
    interpreted = any(position in covered for position in thread)
    if verdict == "not_tried" and not uncovered_text:
        plan.not_tried.append(node)
        return
    if node not in tree.nodes:
        plan.problems.append(f"{node}: no such node, its {verdict} cannot be kept")
        return
    if verdict == "perfect":
        step = acceptance_step_for(tree, session.id, node)
        if isinstance(step, str):
            plan.problems.append(step)
        else:
            plan.acceptances.append(step)
    elif verdict == "needs_work" and (uncovered_text or not interpreted):
        subject = _case_subject(session, node, "rework", thread)
        plan.issues.append(IssueStep("rework", subject, lookup(subject.key)))
    elif verdict != "needs_work" and uncovered_text:
        subject = _case_subject(session, node, "change", thread)
        plan.issues.append(IssueStep("case change", subject, lookup(subject.key)))
    elif verdict == "ok_with_improvements" and not interpreted:
        plan.no_change_named.append(node)


def _is_uncovered_owner_text(comment: Comment, position: int, covered: set[int]) -> bool:
    return comment.role == "owner" and bool(comment.text) and position not in covered


def _plan_general_comments(plan: ChatSessionPlan, covered: set[int], lookup: IssueLookup) -> None:
    session = plan.session
    thread = [i for i, comment in enumerate(session.comments) if comment.case is None]
    if not any(_is_uncovered_owner_text(session.comments[i], i, covered) for i in thread):
        return
    subject = TicketSubject(
        key=change_key(session.id, "general"),
        title=f"Changes the owner asked for in general, in test session {session.id}",
        summary="Comments on no particular case, not interpreted",
        objective=(
            f"The owner commented in test session `{session.id}` on no particular case, and no "
            "interpreter read it: the thread follows, whole. Work out what it asks for, do what is "
            "a change, and say on this issue what you left out and why."
        ),
        messages=_thread_text(session, thread),
        node_id=None,
        is_rework=False,
    )
    plan.issues.append(IssueStep("general", subject, lookup(subject.key)))


def plan_chat_session(
    session: ChatSession,
    tree: Tree,
    *,
    find_issue: IssueLookup,
    feedback_file: pathlib.Path,
) -> ChatSessionPlan:
    plan = ChatSessionPlan(session, verdicts=summarize_verdicts(session, feedback_file))
    items = session.items or ()
    covered = {position for item in items for position in item.from_messages}
    for question in session.questions:
        if question.answer is None:
            continue
        step = answer_step_for(tree, question)
        if isinstance(step, str):
            plan.problems.append(step)
        else:
            plan.answers.append(step)
    for item in items:
        if item.withdrawn:
            plan.withdrawn.append(item)
        elif item.kind == "change":
            _item_step(plan, tree, item, find_issue)
        else:
            plan.kept_for_next_session.append(item)
    nodes = dict.fromkeys(
        [case.node for case in session.cases] + [c.case for c in session.comments if c.case]
    )
    for node in nodes:
        _plan_case(plan, tree, node, covered, find_issue)
    _plan_general_comments(plan, covered, find_issue)
    return plan
