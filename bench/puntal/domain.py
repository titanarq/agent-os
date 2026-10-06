"""The toy domain of the puntal bench, as a reference model: a helpdesk board of tickets.

The puntal improvises behaviour from a Markdown node and persists state through `store.py`. Nothing
about that is checkable unless something else knows what the right state is, so this module is the
oracle: the rules of the five actions as plain code, applied to a store snapshot (`Store.dump()`),
plus the invariants any snapshot must satisfy and the shape each action's response must have.

A snapshot is `{"_counters": {"ticket": N}, "tickets": {"T-1": {...}}, "summary": {"board": {...}}}`.
`tickets` documents carry `id`, `title`, `priority`, `status` and `resolution`; `summary/board` is a
DERIVED document the mutating actions must keep equal to a recount of the tickets.

Every function is pure: it returns new data and never touches a store.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass

# create_ticket, change_status, show_board and board_report are each described by their node; export_csv
# is bound to the show-board node, which says nothing about exporting -- the deliberate gap.
ACTIONS = ("create_ticket", "change_status", "show_board", "board_report", "export_csv")
MUTATING_ACTIONS = ("create_ticket", "change_status")
GAP_ACTIONS = ("export_csv",)
# Which node file each action is bound to.
NODE_FOR_ACTION = {
    "create_ticket": "uc-1-file-a-ticket",
    "change_status": "uc-2-move-a-ticket-along",
    "show_board": "uc-3-see-the-board",
    "board_report": "uc-4-report-on-the-board",
    "export_csv": "uc-3-see-the-board",
}

PRIORITIES = ("low", "normal", "high")
STATUSES = ("open", "in_progress", "resolved")
NEXT_STATUS = {"open": "in_progress", "in_progress": "resolved"}
TICKET_ID_RE = re.compile(r"^T-([1-9]\d*)$")
COMPARED_TICKET_FIELDS = ("id", "title", "priority", "status", "resolution")


@dataclass(frozen=True)
class Violation:
    """One thing that is wrong, with the evidence to check it by hand."""

    code: str
    message: str

    def key(self) -> tuple[str, str]:
        return (self.code, self.message)


def empty_state() -> dict:
    return {"_counters": {}}


def tickets_of(state: dict) -> dict[str, dict]:
    return state.get("tickets") or {}


def ticket_number(ticket_id: str) -> int:
    match = TICKET_ID_RE.match(ticket_id)
    return int(match.group(1)) if match else 0


def sorted_ticket_ids(state: dict) -> list[str]:
    return sorted(tickets_of(state), key=ticket_number)


def recount(state: dict) -> dict:
    counts = {status: 0 for status in STATUSES}
    for ticket in tickets_of(state).values():
        if ticket.get("status") in counts:
            counts[ticket["status"]] += 1
    return {**counts, "total": len(tickets_of(state))}


def oldest_unresolved(state: dict) -> str | None:
    unresolved = [
        i for i in sorted_ticket_ids(state) if tickets_of(state)[i].get("status") != "resolved"
    ]
    return unresolved[0] if unresolved else None


def high_priority_unresolved(state: dict) -> list[str]:
    return [
        i
        for i in sorted_ticket_ids(state)
        if tickets_of(state)[i].get("priority") == "high"
        and tickets_of(state)[i].get("status") != "resolved"
    ]


# ---------------------------------------------------------------------------------------------
# The rules.
# ---------------------------------------------------------------------------------------------
def apply_action(state: dict, action: str, payload: dict) -> tuple[dict, dict | None]:
    """`(state after, expectation)`. The expectation is what a mutating action's response must say --
    `{"ok": bool, "ticket_id": str, "status": str | None}` -- and None for the actions that only
    read. A refused action returns the state unchanged: a refusal never writes."""
    after = copy.deepcopy(state)
    if action == "create_ticket":
        title = str(payload.get("title") or "").strip()
        priority = payload.get("priority") or "normal"
        number = after["_counters"].get("ticket", 0) + 1
        ticket_id = f"T-{number}"
        after["_counters"]["ticket"] = number
        after.setdefault("tickets", {})[ticket_id] = {
            "id": ticket_id,
            "title": title,
            "priority": priority,
            "status": "open",
            "resolution": None,
        }
        after.setdefault("summary", {})["board"] = recount(after)
        return after, {"ok": True, "ticket_id": ticket_id, "status": "open"}
    if action == "change_status":
        ticket_id = str(payload.get("id") or "")
        target = payload.get("status")
        note = str(payload.get("note") or "").strip()
        ticket = tickets_of(after).get(ticket_id)
        if ticket is None:
            return state, {"ok": False, "ticket_id": ticket_id, "status": None}
        if NEXT_STATUS.get(ticket["status"]) != target:
            return state, {"ok": False, "ticket_id": ticket_id, "status": None}
        if target == "resolved" and not note:
            return state, {"ok": False, "ticket_id": ticket_id, "status": None}
        ticket["status"] = target
        ticket["resolution"] = note if target == "resolved" else None
        after.setdefault("summary", {})["board"] = recount(after)
        return after, {"ok": True, "ticket_id": ticket_id, "status": target}
    return state, None


# ---------------------------------------------------------------------------------------------
# Invariants: what any snapshot of the store must satisfy, whoever wrote it.
# ---------------------------------------------------------------------------------------------
def check_invariants(state: dict) -> list[Violation]:
    violations: list[Violation] = []
    tickets = tickets_of(state)
    for key, ticket in tickets.items():
        if ticket.get("id") != key or not TICKET_ID_RE.match(key):
            violations.append(
                Violation("ticket_id", f"document {key!r} carries id {ticket.get('id')!r}")
            )
        if ticket.get("status") not in STATUSES:
            violations.append(
                Violation("ticket_status", f"{key} has status {ticket.get('status')!r}")
            )
        if ticket.get("priority") not in PRIORITIES:
            violations.append(
                Violation("ticket_priority", f"{key} has priority {ticket.get('priority')!r}")
            )
        if not str(ticket.get("title") or "").strip():
            violations.append(Violation("ticket_title", f"{key} has no title"))
        resolved = ticket.get("status") == "resolved"
        has_resolution = bool(str(ticket.get("resolution") or "").strip())
        if resolved != has_resolution:
            violations.append(
                Violation(
                    "ticket_resolution",
                    f"{key} is {ticket.get('status')!r} with resolution {ticket.get('resolution')!r}",
                )
            )
    numbers = sorted(ticket_number(key) for key in tickets)
    counter = state.get("_counters", {}).get("ticket", 0)
    if numbers != list(range(1, len(numbers) + 1)):
        violations.append(
            Violation(
                "ticket_ids_not_sequential", f"ticket numbers {numbers} are not 1..{len(numbers)}"
            )
        )
    if counter != (numbers[-1] if numbers else 0):
        violations.append(
            Violation(
                "counter_mismatch",
                f"the ticket counter reads {counter} and the highest ticket is "
                f"{numbers[-1] if numbers else 0}",
            )
        )
    summary = (state.get("summary") or {}).get("board")
    if tickets and summary is None:
        violations.append(Violation("summary_missing", "tickets exist and summary/board does not"))
    elif summary is not None and summary != recount(state):
        violations.append(
            Violation(
                "summary_stale", f"summary/board says {summary} and a recount says {recount(state)}"
            )
        )
    return violations


def diff_states(expected: dict, actual: dict) -> list[Violation]:
    """Where `actual` is not what the rules say it should be. Fields the rules do not mention (a
    timestamp the puntal chose to add) are not compared."""
    violations: list[Violation] = []
    expected_tickets, actual_tickets = tickets_of(expected), tickets_of(actual)
    for ticket_id in sorted(set(expected_tickets) | set(actual_tickets), key=ticket_number):
        want, got = expected_tickets.get(ticket_id), actual_tickets.get(ticket_id)
        if want is None:
            violations.append(
                Violation("ticket_unexpected", f"{ticket_id} exists and should not: {got}")
            )
        elif got is None:
            violations.append(
                Violation("ticket_missing", f"{ticket_id} is missing; expected {want}")
            )
        else:
            for field in COMPARED_TICKET_FIELDS:
                if _normalised(want.get(field)) != _normalised(got.get(field)):
                    violations.append(
                        Violation(
                            "ticket_field",
                            f"{ticket_id}.{field} is {got.get(field)!r}; expected {want.get(field)!r}",
                        )
                    )
    want_counter = expected.get("_counters", {}).get("ticket", 0)
    got_counter = actual.get("_counters", {}).get("ticket", 0)
    if want_counter != got_counter:
        violations.append(
            Violation("counter_value", f"ticket counter is {got_counter}; expected {want_counter}")
        )
    return violations


def _normalised(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


# ---------------------------------------------------------------------------------------------
# Responses.
# ---------------------------------------------------------------------------------------------
def parse_response(text: str) -> dict | None:
    """The JSON object a response carries, tolerating a markdown fence around it; None when there
    is none."""
    candidate = text.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", candidate, re.DOTALL)
    if fenced:
        candidate = fenced.group(1)
    try:
        value = json.loads(candidate)
    except ValueError:
        start, end = candidate.find("{"), candidate.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            value = json.loads(candidate[start : end + 1])
        except ValueError:
            return None
    return value if isinstance(value, dict) else None


def _expect(
    violations: list[Violation], code: str, label: str, wanted: object, got: object
) -> None:
    if wanted != got:
        violations.append(
            Violation(code, f"{label}: the response says {got!r}; the store says {wanted!r}")
        )


def check_response(
    action: str, payload: dict, response: dict | None, before: dict, after: dict
) -> list[Violation]:
    """The response of one invocation against the state it should describe. `before` and `after`
    are the snapshots around the invocation: a read is checked against `after` (equal to `before`
    for a read that behaved), a write against what the rules say the write was."""
    if response is None and action != "export_csv":
        return [Violation("response_not_json", f"{action}: the response is not a JSON object")]
    violations: list[Violation] = []
    if action == "create_ticket":
        _, expectation = apply_action(before, action, payload)
        _expect(
            violations,
            "response_ticket_id",
            "create_ticket ticket_id",
            expectation["ticket_id"],
            response.get("ticket_id"),
        )
        _expect(violations, "response_ok", "create_ticket ok", True, response.get("ok"))
    elif action == "change_status":
        _, expectation = apply_action(before, action, payload)
        _expect(
            violations,
            "response_ok",
            f"change_status {expectation['ticket_id']} ok",
            expectation["ok"],
            response.get("ok"),
        )
        if expectation["ok"]:
            _expect(
                violations,
                "response_status",
                f"change_status {expectation['ticket_id']} status",
                expectation["status"],
                response.get("status"),
            )
    elif action == "show_board":
        listed = response.get("tickets")
        if not isinstance(listed, list):
            return [Violation("response_shape", "show_board: `tickets` is not a list")]
        wanted_ids = sorted_ticket_ids(after)
        got_ids = [t.get("id") for t in listed if isinstance(t, dict)]
        _expect(violations, "response_board_ids", "show_board ticket ids", wanted_ids, got_ids)
        for entry in listed:
            stored = tickets_of(after).get(entry.get("id")) if isinstance(entry, dict) else None
            if stored is None:
                continue
            for field in ("title", "priority", "status"):
                _expect(
                    violations,
                    "response_board_field",
                    f"show_board {entry['id']}.{field}",
                    stored.get(field),
                    entry.get(field),
                )
        _expect(
            violations,
            "response_board_counts",
            "show_board counts",
            recount(after),
            response.get("counts"),
        )
    elif action == "board_report":
        counts = response.get("counts") or {}
        _expect(
            violations,
            "response_report_counts",
            "board_report counts",
            {k: recount(after)[k] for k in STATUSES},
            {k: counts.get(k) for k in STATUSES},
        )
        _expect(
            violations,
            "response_report_total",
            "board_report total",
            recount(after)["total"],
            response.get("total"),
        )
        _expect(
            violations,
            "response_report_oldest",
            "board_report oldest_unresolved",
            oldest_unresolved(after),
            response.get("oldest_unresolved"),
        )
        _expect(
            violations,
            "response_report_high",
            "board_report high_priority_unresolved",
            high_priority_unresolved(after),
            sorted(response.get("high_priority_unresolved") or [], key=ticket_number),
        )
    return violations


def check_response_text(
    action: str, payload: dict, response_text: str, before: dict, after: dict
) -> list[Violation]:
    """`check_response` for the raw text of a response: parsed first, and for `export_csv` -- whose
    node specifies no form -- only the ticket ids it names are checked against the store."""
    if action == "export_csv":
        named = set(re.findall(r"\bT-[1-9]\d*\b", response_text))
        return [
            Violation(
                "response_unknown_ticket", f"export_csv names {ticket_id}, which the store lacks"
            )
            for ticket_id in sorted(named - set(tickets_of(after)), key=ticket_number)
        ]
    return check_response(action, payload, parse_response(response_text), before, after)
