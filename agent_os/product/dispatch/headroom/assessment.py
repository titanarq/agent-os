"""Whether each ready ticket would start now, and what it waits for when it would not."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from agent_os.product.dispatch.headroom.slot_ledger import IssueRow, SlotLedger
from agent_os.product.dispatch.rules import tree_dispatch_refusals

COULD_START_NOW = "could-start-now"
WAITS_ONLY_FOR_THE_CAP = "waits-only-for-the-cap"
WAITS = "waits"
NOT_RUNNING_YET = "that ticket is not running yet: it is ahead of this one in this pass"


@dataclass(frozen=True)
class TicketAssessment:
    number: int
    verdict: str
    reasons: tuple[str, ...] = ()


def assess_ready_tickets(
    ready_rows: Sequence[IssueRow],
    open_rows: Sequence[IssueRow],
    running_rows: Sequence[IssueRow],
    ledger: SlotLedger,
) -> list[TicketAssessment]:
    """Try the ready tickets in issue order the way a planner would, each against what is running and
    against the tickets ahead of it that are clear of every rule but the cap: of two tickets on the
    same code only the first is ever clear, so the second waits for the first and not for the cap.
    `ledger` is left as it was: the room the starters would take is counted on a copy."""
    ledger = ledger.copy()
    ahead: list[IssueRow] = []
    assessments = []
    for row in sorted(ready_rows, key=lambda candidate: int(candidate["number"])):
        number = int(row["number"])
        running_refusals = tree_dispatch_refusals(row, open_rows, running_rows)
        ahead_refusals = [
            f"{refusal} ({NOT_RUNNING_YET})"
            for refusal in tree_dispatch_refusals(row, open_rows, [*running_rows, *ahead])
            if refusal not in running_refusals
        ]
        if running_refusals or ahead_refusals:
            assessments.append(
                TicketAssessment(number, WAITS, (*running_refusals, *ahead_refusals))
            )
            continue
        ahead.append(row)
        cap_refusal = ledger.refusal_for(row)
        if cap_refusal:
            assessments.append(TicketAssessment(number, WAITS_ONLY_FOR_THE_CAP, (cap_refusal,)))
            continue
        ledger.take(row)
        assessments.append(TicketAssessment(number, COULD_START_NOW))
    return assessments
