"""What ingesting one closed test session would do, decided without changing anything.

The plan is a pure function of the session, the tree and what the tracker already holds, so the
same plan is what `test-ingest` prints by default and what `--apply` carries out
(`docs/adr/2026-10-09-a-closed-test-session-is-ingested-by-a-command-that-plans-first.md`).

- an answered question is written into its node (the owner's words, exactly);
- a question left unanswered is left alone: its default answer stands, as it did in the app;
- a rejected case becomes a rework ticket for its node;
- an accepted case is recorded on its node as the owner's acceptance;
- a case not tried is left alone.

A step that is already done (the question answered with these very words, the acceptance recorded,
the ticket opened) says so and is not repeated. A step that cannot be done (a node the tree does not
have, a question the node does not carry open) is a problem, never silently dropped.
"""

from __future__ import annotations

import pathlib
from collections.abc import Callable
from dataclasses import dataclass, field

from agent_os.product.session_ingest.feedback_summary import ActionVerdicts, summarize_verdicts
from agent_os.product.session_ingest.session_file import Case, ClosedSession, Question
from agent_os.product.tree.loader import Tree

# (session id, node id) -> the number of the issue already opened for that rejection, or None.
ReworkLookup = Callable[[str, str], int | None]


@dataclass(frozen=True)
class AnswerStep:
    question: Question
    already_written: bool


@dataclass(frozen=True)
class AcceptanceStep:
    node: str
    already_recorded: bool


@dataclass(frozen=True)
class ReworkStep:
    case: Case
    existing_issue: int | None


@dataclass
class SessionPlan:
    session: ClosedSession
    answers: list[AnswerStep] = field(default_factory=list)
    unanswered: list[Question] = field(default_factory=list)
    acceptances: list[AcceptanceStep] = field(default_factory=list)
    reworks: list[ReworkStep] = field(default_factory=list)
    not_tried: list[Case] = field(default_factory=list)
    verdicts: list[ActionVerdicts] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def _plan_answer(plan: SessionPlan, tree: Tree, question: Question) -> None:
    node = tree.nodes.get(question.node)
    if node is None:
        plan.problems.append(f"{question.node}: no such node, its answer cannot be written")
        return
    same_text = [e for e in node.experiments if e.kind == "question" and e.scope == "what"]
    same_text = [e for e in same_text if e.question == question.question]
    if any(e.outcome == "open" for e in same_text):
        plan.answers.append(AnswerStep(question, already_written=False))
    elif any(e.outcome == "answered" and e.finding == question.answer for e in same_text):
        plan.answers.append(AnswerStep(question, already_written=True))
    elif any(e.outcome == "answered" for e in same_text):
        plan.problems.append(
            f"{question.node}: {question.question!r} is already answered with other words; the "
            "answer of this session is not written, the owner decides which stands"
        )
    else:
        plan.problems.append(
            f"{question.node}: no open question of what reads {question.question!r}"
        )


def plan_session(
    session: ClosedSession,
    tree: Tree,
    *,
    find_rework_issue: ReworkLookup,
    feedback_file: pathlib.Path,
) -> SessionPlan:
    plan = SessionPlan(session, verdicts=summarize_verdicts(session, feedback_file))
    for question in session.questions:
        if question.answer is None:
            plan.unanswered.append(question)
        else:
            _plan_answer(plan, tree, question)
    for case in session.cases:
        if case.verdict == "not_tried":
            plan.not_tried.append(case)
        elif case.node not in tree.nodes:
            plan.problems.append(f"{case.node}: no such node, its {case.verdict} cannot be kept")
        elif case.verdict == "accept":
            recorded = any(a.session == session.id for a in tree.nodes[case.node].acceptances)
            plan.acceptances.append(AcceptanceStep(case.node, recorded))
        else:
            plan.reworks.append(ReworkStep(case, find_rework_issue(session.id, case.node)))
    return plan
