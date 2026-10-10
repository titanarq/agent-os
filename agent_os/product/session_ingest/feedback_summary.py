"""The owner's verdicts on improvised answers during one test session, as an input to the plan.

`.cache/puntal/feedback.jsonl` (`agent_os.product.puntal.telemetry.feedback`) holds one line per
verdict the owner gave a puntal's answer: accept, reject with a note, or retry. A verdict does not
know which test session it was given in, so it belongs to the session whose window
(`opened_at` .. `closed_at`, with no end while the session is open) contains its `recorded_at`: the owner gives them by hand inside the
app, so the window is the only join the two files have, and it is said so wherever it is shown.

Nothing is written from this yet; it is the insumo the hardening order and the puntals' prompts
will read (`docs/tree/dec-usage-telemetry-from-one-real-human.md`).
"""

from __future__ import annotations

import datetime
import pathlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from agent_os.product.records import read_json_lines

if TYPE_CHECKING:
    from agent_os.product.session_ingest.session_file import AnySession


@dataclass
class ActionVerdicts:
    action: str
    node: str
    accepted: int = 0
    retried: int = 0
    rejected_because: list[str] = field(default_factory=list)


def _recorded_at(row: dict) -> datetime.datetime | None:
    try:
        moment = datetime.datetime.fromisoformat(str(row.get("recorded_at")))
    except ValueError:
        return None
    return moment if moment.tzinfo else None


def summarize_verdicts(session: AnySession, feedback_file: pathlib.Path) -> list[ActionVerdicts]:
    """The verdicts recorded inside the session's window, one row per action and node, in the order
    each was first given. An absent file is an empty summary: the session may have judged nothing
    improvised. A line with no readable moment is skipped, never placed in a session by guess."""
    rows: dict[tuple[str, str], ActionVerdicts] = {}
    for record in read_json_lines(feedback_file):
        moment = _recorded_at(record)
        if moment is None or moment < session.opened_at:
            continue
        if session.closed_at is not None and moment > session.closed_at:
            continue
        key = (str(record.get("action") or "?"), str(record.get("node") or "?"))
        row = rows.setdefault(key, ActionVerdicts(*key))
        verdict = record.get("verdict")
        if verdict == "accept":
            row.accepted += 1
        elif verdict == "retry":
            row.retried += 1
        elif verdict == "reject":
            row.rejected_because.append(str(record.get("note") or "").strip() or "(no note)")
    return list(rows.values())
