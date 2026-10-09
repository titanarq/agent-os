"""The two shapes of the answer: a line per ticket and a summary line, or the same as JSON."""

from __future__ import annotations

import json
from collections.abc import Sequence

from agent_os.product.dispatch.headroom.assessment import (
    COULD_START_NOW,
    WAITS,
    WAITS_ONLY_FOR_THE_CAP,
    TicketAssessment,
)
from agent_os.product.dispatch.headroom.slot_ledger import SlotLedger


def _numbers(assessments: Sequence[TicketAssessment], verdict: str) -> list[int]:
    return [item.number for item in assessments if item.verdict == verdict]


def summary_line(assessments: Sequence[TicketAssessment]) -> str:
    line = (
        f"{len(_numbers(assessments, COULD_START_NOW))} could start now; "
        f"{len(_numbers(assessments, WAITS_ONLY_FOR_THE_CAP))} wait only for the cap"
    )
    waiting_for_something_else = len(_numbers(assessments, WAITS))
    if waiting_for_something_else:
        line += f"; {waiting_for_something_else} wait for something else"
    return line


def _ticket_line(assessment: TicketAssessment) -> str:
    if assessment.verdict == COULD_START_NOW:
        return f"#{assessment.number}  could start now"
    label = "waits only for the cap" if assessment.verdict == WAITS_ONLY_FOR_THE_CAP else "waits"
    return f"#{assessment.number}  {label}: {'; '.join(assessment.reasons)}"


def render_text(assessments: Sequence[TicketAssessment], ledger: SlotLedger) -> str:
    lines = [f"slots: {ledger.summary()}"]
    lines += [_ticket_line(assessment) for assessment in assessments]
    lines.append(summary_line(assessments))
    return "\n".join(lines)


def render_json(assessments: Sequence[TicketAssessment], ledger: SlotLedger) -> str:
    return json.dumps(
        {
            "max_parallel_issues": ledger.max_parallel_issues,
            "running": ledger.running_total,
            "tickets": [
                {"number": item.number, "verdict": item.verdict, "reasons": list(item.reasons)}
                for item in assessments
            ],
            "could_start_now": _numbers(assessments, COULD_START_NOW),
            "wait_only_for_the_cap": _numbers(assessments, WAITS_ONLY_FOR_THE_CAP),
        },
        indent=2,
    )
