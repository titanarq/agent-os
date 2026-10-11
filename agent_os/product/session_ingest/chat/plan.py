"""What ingesting one chat session, open or closed, would do, decided without changing anything.

The owner's words are split by the interpreter into items (`docs/FEEDBACK_INTERPRETER.md`); each item
points at the messages it came from (`from_messages`). From there:

- a `change` that is not withdrawn becomes one issue, directly, unless it is `proposed` (it waits for the owner's yes);
- an approved `puntal_change` becomes one issue on `sessions.mechanism_repository` (`chat/puntal_change.py`);
- a `decision` is NOT launched: it is kept for the owner to confirm when the next session opens;
- a `question_of_what` is kept the same way, as an open question;
- a withdrawn item is nothing;
- a case whose last state is `perfect` is recorded on its node as the owner's acceptance;
- the owner's text that no item covers (a session closed before the interpreter was connected, or a
  message the interpreter could not read) is never dropped: by the last state of its case, `needs_work`
  returns as rework and `ok_with_improvements` as a change, each quoting the thread of the case, and a
  comment on no case as one general change that says no interpreter read it.

An open session is read as it stands, again on every run (the app has no button that closes it), so
what is launched must stay right when more messages arrive: an item is keyed by its own id and so
is launched once, wherever it came from; but an issue by the state of a case quotes the thread of the
case once and is keyed by the case, so a message added afterwards would never reach it, and it would
duplicate an item that arrives later. So in an open session that text **waits** (the plan says what)
and is handled as above when the session closes. A `perfect` is accepted at once, on the day the
session opened.

A step already done (the answer written, the acceptance recorded, the issue opened) says so and is
not repeated; a step that cannot be done (a node the tree lacks) is a problem, never dropped.
"""

from __future__ import annotations

import pathlib
from collections.abc import Callable
from dataclasses import dataclass, field

from agent_os.product.session_ingest.chat.model import ChatSession, Comment, Item
from agent_os.product.session_ingest.chat.proposals import HeldText, is_awaiting_approval
from agent_os.product.session_ingest.chat.puntal_change import (
    PUNTAL_CHANGE_ORIGIN,
    decide_puntal_change,
)
from agent_os.product.session_ingest.chat.ticket import (
    TicketSubject,
    case_subject,
    change_key,
    item_origin_sentence,
    one_safe_line,
    read_from_the_same_messages,
    thread_text,
)
from agent_os.product.session_ingest.chat.verdicts import VerdictStep, verdict_step_for
from agent_os.product.session_ingest.feedback_summary import ActionVerdicts, summarize_verdicts
from agent_os.product.session_ingest.plan import (
    AcceptanceStep,
    AnswerStep,
    acceptance_step_for,
    answer_step_for,
)
from agent_os.product.tree.loader import Tree

# `<!-- key: -->` -> the number of the issue already opened for it, or None.
IssueLookup = Callable[[str], int | None]


@dataclass(frozen=True)
class IssueStep:
    """`origin` is why the issue exists: `item`, `rework`, `case change` or `general`."""

    origin: str
    subject: TicketSubject
    existing_issue: int | None
    on_mechanism: bool = False


@dataclass
class ChatSessionPlan:
    session: ChatSession
    answers: list[AnswerStep] = field(default_factory=list)
    acceptances: list[AcceptanceStep] = field(default_factory=list)
    issues: list[IssueStep] = field(default_factory=list)
    kept_for_next_session: list[Item] = field(default_factory=list)
    withdrawn: list[Item] = field(default_factory=list)
    withdrawn_after_launch: list[tuple[Item, int]] = field(default_factory=list)
    confirm_before_dispatch: bool = False
    proposals: list[Item] = field(default_factory=list)
    held: list[HeldText] = field(default_factory=list)
    waiting: list[str] = field(default_factory=list)
    no_change_named: list[str] = field(default_factory=list)
    not_tried: list[str] = field(default_factory=list)
    verdicts: list[ActionVerdicts] = field(default_factory=list)
    verdict_steps: list[VerdictStep] = field(default_factory=list)
    held_puntal_changes: list[Item] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def _item_step(plan: ChatSessionPlan, tree: Tree, item: Item, lookup: IssueLookup) -> None:
    if is_awaiting_approval(item, confirm_before_dispatch=plan.confirm_before_dispatch):
        plan.proposals.append(item)
        return
    if item.node is not None and item.node not in tree.nodes:
        if plan.confirm_before_dispatch:
            plan.proposals.append(item)
        plan.problems.append(
            f"{item.id}: no such node {item.node!r}, its change cannot be launched"
        )
        return
    where = f" (page {item.page})" if item.page else ""
    summary = one_safe_line(item.summary)
    key = change_key(plan.session.id, f"item.{item.id}")
    subject = TicketSubject(
        key=key,
        title=f"{summary} (test session {plan.session.id}, {item.id})",
        summary=summary,
        task=summary,
        origin=item_origin_sentence(item, plan.session.id, where),
        messages=thread_text(plan.session, list(item.from_messages)),
        node_id=item.node,
        is_rework=False,
        others=read_from_the_same_messages(
            plan.session, list(item.from_messages), apart_from=item.id
        ),
    )
    plan.issues.append(IssueStep("item", subject, lookup(key)))


def _verdict_item(plan: ChatSessionPlan, item: Item, feedback_file: pathlib.Path) -> None:
    if is_awaiting_approval(item, confirm_before_dispatch=plan.confirm_before_dispatch):
        plan.proposals.append(item)
        return
    step = verdict_step_for(plan.session.id, item, feedback_file=feedback_file)
    if isinstance(step, str):
        plan.problems.append(step)
    else:
        plan.verdict_steps.append(step)


def _puntal_change_item(
    plan: ChatSessionPlan, tree: Tree, item: Item, lookup: IssueLookup | None, **context
) -> None:
    outcome = decide_puntal_change(plan.session, tree, item, **context)
    plan.proposals.extend(outcome.proposals)
    plan.held_puntal_changes.extend(outcome.held)
    plan.problems.extend(outcome.problems)
    if outcome.subject and lookup:
        existing = lookup(outcome.subject.key)
        plan.issues.append(IssueStep(PUNTAL_CHANGE_ORIGIN, outcome.subject, existing, True))


def _launch_or_wait(plan: ChatSessionPlan, origin: str, subject: TicketSubject, lookup) -> None:
    if plan.confirm_before_dispatch:
        plan.held.append(HeldText(subject.summary, subject.node_id))
    elif plan.session.is_open:
        plan.waiting.append(subject.title)
    else:
        plan.issues.append(IssueStep(origin, subject, lookup(subject.key)))


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
        _launch_or_wait(plan, "rework", case_subject(session, node, "rework", thread), lookup)
    elif verdict != "needs_work" and uncovered_text:
        _launch_or_wait(plan, "case change", case_subject(session, node, "change", thread), lookup)
    elif verdict == "ok_with_improvements" and not interpreted and not session.is_open:
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
        task=(
            "Work out what the thread asks for, do what is a change, and say on this issue what "
            "you left out and why."
        ),
        origin=(
            f"The owner commented in test session `{session.id}` on no particular case, and no "
            "interpreter read it: the whole thread is quoted below."
        ),
        messages=thread_text(session, thread),
        node_id=None,
        is_rework=False,
        others=read_from_the_same_messages(session, thread),
    )
    _launch_or_wait(plan, "general", subject, lookup)


def plan_chat_session(
    session: ChatSession,
    tree: Tree,
    *,
    find_issue: IssueLookup,
    feedback_file: pathlib.Path,
    confirm_before_dispatch: bool = False,
    mechanism_repository: str = "",
    find_mechanism_issue: IssueLookup | None = None,
) -> ChatSessionPlan:
    plan = ChatSessionPlan(
        session,
        verdicts=summarize_verdicts(session, feedback_file),
        confirm_before_dispatch=confirm_before_dispatch,
    )
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
            launched = find_issue(change_key(session.id, f"item.{item.id}"))
            if item.kind == "change" and launched is not None:
                plan.withdrawn_after_launch.append((item, launched))
        elif item.kind == "change":
            _item_step(plan, tree, item, find_issue)
        elif item.kind == "verdict":
            _verdict_item(plan, item, feedback_file)
        elif item.kind == "puntal_change":
            _puntal_change_item(
                plan,
                tree,
                item,
                find_mechanism_issue,
                repository=mechanism_repository,
                feedback_file=feedback_file,
                confirm_before_dispatch=confirm_before_dispatch,
            )
        else:
            plan.kept_for_next_session.append(item)
    nodes = dict.fromkeys(
        [case.node for case in session.cases] + [c.case for c in session.comments if c.case]
    )
    for node in nodes:
        _plan_case(plan, tree, node, covered, find_issue)
    _plan_general_comments(plan, covered, find_issue)
    return plan
