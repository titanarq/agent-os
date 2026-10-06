"""The fast path of the fake `claude`: a perfect puntal that PLANS in one turn, for the helpdesk bench.

It reads what the driver's pre-helper loaded into the brief (`# State loaded for this action`) and
answers with the plan JSON of `agent_os.product.puntal.fast.operations`, never calling a tool. An
action whose node did not declare the reads it needs gets `{"needs_state": ...}`, which is how the
bench shows the slow path being taken and marked.

Faults (`FAKE_PUNTAL_FAULT`) that only make sense here: `bad_plan_once` (the first invocation of a
state directory sends an invalid plan, the retry a good one) and `update_missing_ticket` (the plan
updates a ticket that is not there, the executor refuses it, the retry says so).
"""

from __future__ import annotations

import json
import os
import re

import domain

SKIPPED_OR_FAILED = ("skipped:", "failed (")


def loaded_reads(loaded_section: str) -> dict[str, str]:
    """`{read command: its output}` from the brief's loaded-state section."""
    reads: dict[str, str] = {}
    for block in re.split(r"(?m)^## ", loaded_section)[1:]:
        command, _, output = block.partition("\n")
        reads[command.strip()] = output.strip()
    return reads


def _tickets(reads: dict[str, str]) -> list[dict] | None:
    output = reads.get("list tickets")
    if output is None or output.startswith(SKIPPED_OR_FAILED):
        return None
    return json.loads(output)


def _counts(tickets: list[dict]) -> dict:
    counts = {s: sum(1 for t in tickets if t["status"] == s) for s in domain.STATUSES}
    return {**counts, "total": len(tickets)}


def _needs(what: str) -> dict:
    return {"needs_state": what}


def _is_retry(brief: str) -> bool:
    return "# Your previous plan was rejected" in brief


def _state_dir_flag(name: str) -> str | None:
    state_dir = os.environ.get("FAKE_PUNTAL_STATE_DIR")
    if not state_dir:
        return None
    os.makedirs(state_dir, exist_ok=True)
    return os.path.join(state_dir, name)


def _first_time(name: str) -> bool:
    marker = _state_dir_flag(name)
    if marker is None or os.path.exists(marker):
        return False
    open(marker, "a").close()
    return True


def _new_ticket_operations(payload: dict) -> list[dict]:
    return [
        {"op": "allocate", "counter": "ticket", "bind": "n"},
        {
            "op": "put",
            "collection": "tickets",
            "id": "T-{{n}}",
            "document": {
                "id": "T-{{n}}",
                "title": str(payload.get("title", "")).strip(),
                "priority": payload.get("priority") or "normal",
                "status": "open",
                "resolution": None,
            },
        },
    ]


def _plan_create(payload: dict, reads: dict, fault: str, brief: str) -> dict:
    if fault == "bad_plan_once" and _first_time("bad-plan-seen"):
        return {"operations": [{"op": "upsert"}], "answer": "x"}
    operations = _new_ticket_operations(payload)
    if fault == "reuse_last_id":
        tickets = _tickets(reads)
        if tickets:
            reused = tickets[-1]["id"]
            operations = [
                {
                    **operations[1],
                    "id": reused,
                    "document": {**operations[1]["document"], "id": reused},
                }
            ]
            return {"operations": operations, "answer": {"ok": True, "ticket_id": reused}}
    return {"operations": operations, "answer": {"ok": True, "ticket_id": "T-{{n}}"}}


def _plan_change(payload: dict, reads: dict, fault: str, brief: str) -> dict:
    ticket_id, target = str(payload.get("id", "")), payload.get("status")
    note = str(payload.get("note") or "").strip()
    key = f"get tickets {ticket_id}"
    if key not in reads:
        return _needs(f"the ticket {ticket_id}")
    if fault == "update_missing_ticket" and not _is_retry(brief):
        return {
            "operations": [
                {
                    "op": "update",
                    "collection": "tickets",
                    "id": "T-404",
                    "changes": {"status": target},
                }
            ],
            "answer": {"ok": True, "ticket_id": "T-404", "status": target},
        }
    output = reads[key]
    refusal = None
    if output.startswith(SKIPPED_OR_FAILED) or _is_retry(brief):
        refusal = "no such ticket"
    else:
        ticket = json.loads(output)
        if (
            fault != "accept_invalid_transition"
            and domain.NEXT_STATUS.get(ticket["status"]) != target
        ):
            refusal = f"a {ticket['status']} ticket cannot become {target}"
        elif target == "resolved" and not note:
            refusal = "a resolved ticket needs a note"
    if refusal:
        return {
            "operations": [],
            "answer": {"ok": False, "ticket_id": ticket_id, "reason": refusal},
        }
    return {
        "operations": [
            {
                "op": "update",
                "collection": "tickets",
                "id": ticket_id,
                "changes": {"status": target, "resolution": note if target == "resolved" else None},
            }
        ],
        "answer": {"ok": True, "ticket_id": ticket_id, "status": target},
    }


def _plan_read(action: str, reads: dict, fault: str) -> dict:
    tickets = _tickets(reads)
    if tickets is None:
        return _needs("the list of tickets")
    operations: list[dict] = []
    if fault == "lose_ticket" and action == "show_board":
        operations = [{"op": "delete", "collection": "tickets", "id": "T-1"}]
    counts = _counts(tickets)
    if action == "show_board":
        board = [{k: t[k] for k in ("id", "title", "priority", "status")} for t in tickets]
        return {"operations": operations, "answer": {"tickets": board, "counts": counts}}
    if action == "board_report":
        unresolved = [t for t in tickets if t["status"] != "resolved"]
        reported = dict(counts)
        if fault == "wrong_count":
            reported["open"] += 1
        return {
            "operations": [],
            "answer": {
                "total": len(tickets),
                "counts": {k: v for k, v in reported.items() if k != "total"},
                "oldest_unresolved": unresolved[0]["id"] if unresolved else None,
                "high_priority_unresolved": [
                    t["id"] for t in unresolved if t["priority"] == "high"
                ],
            },
        }
    rows = ["id,title,priority,status"] + [
        f'{t["id"]},"{t["title"]}",{t["priority"]},{t["status"]}' for t in tickets
    ]
    plan = {"operations": [], "answer": "\n".join(rows)}
    if fault != "no_gap_note":
        plan["gap"] = "asked for a CSV export; the node does not describe it"
    return plan


def plan_domain(action: str, payload: dict, loaded_section: str, fault: str, brief: str) -> dict:
    reads = loaded_reads(loaded_section)
    if action == "calibrate":
        return {"operations": [], "answer": {"ok": True}}
    if action == "calibrate_tool":
        return _needs("the list of tickets")
    if action == "create_ticket":
        return _plan_create(payload, reads, fault, brief)
    if action == "change_status":
        return _plan_change(payload, reads, fault, brief)
    if action in ("show_board", "board_report", "export_csv"):
        return _plan_read(action, reads, fault)
    return {"operations": [], "answer": {"ok": False, "reason": f"unknown action {action}"}}
