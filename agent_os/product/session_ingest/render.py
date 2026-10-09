"""The plan of a session as the lines `test-ingest` prints; nothing here decides anything."""

from __future__ import annotations

from agent_os.product.session_ingest.plan import SessionPlan


def _done(already: bool) -> str:
    return " (already done)" if already else ""


def render_plan(plan: SessionPlan) -> list[str]:
    session = plan.session
    lines = [f"session {session.id} (branch {session.branch}, closed {session.closed_at:%Y-%m-%d})"]
    for step in plan.answers:
        verb = "answered" if step.already_written else "write answer"
        lines.append(
            f"  {verb}: {step.question.node}: {step.question.question} -> {step.question.answer}"
            f"{_done(step.already_written)}"
        )
    for question in plan.unanswered:
        lines.append(
            f"  unanswered: {question.node}: {question.question} -- nothing written, the default "
            f"stands meanwhile: {question.default_answer}"
        )
    for acceptance in plan.acceptances:
        lines.append(
            f"  accepted: {acceptance.node} -> record the owner's acceptance"
            f"{_done(acceptance.already_recorded)}"
        )
    for rework in plan.reworks:
        existing = f" (already opened as #{rework.existing_issue})" if rework.existing_issue else ""
        note = rework.case.note or "(no note)"
        lines.append(f"  rejected: {rework.case.node} -> rework issue{existing}: {note}")
    for case in plan.not_tried:
        lines.append(f"  not tried: {case.node} -- nothing written")
    if plan.verdicts:
        lines.append("  verdicts on improvised answers during the session (window of the session):")
    for row in plan.verdicts:
        reasons = "; ".join(row.rejected_because)
        rejected = f", rejected {len(row.rejected_because)} ({reasons})" if reasons else ""
        lines.append(
            f"    {row.action} on {row.node}: accepted {row.accepted}{rejected}, retried {row.retried}"
        )
    lines.extend(f"  problem: {problem}" for problem in plan.problems)
    return lines
