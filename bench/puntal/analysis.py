"""What the puntal bench's raw files say: latency, cost and coherence, computed from them and from
nothing else.

Two raw files feed this, both written by `measure.py` and both append-only JSON lines:

- the TELEMETRY file: the driver's own record of each invocation (`agent_os/product/puntal.py`);
- the TRACE file: what the harness saw around each invocation -- the action, its payload, the whole
  store before and after -- which only the harness can know.

They are joined on `invocation_id`. Everything below is pure, so the same files always give the same
report, and a test can hand it a trace it wrote by hand.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field

import domain


# ---------------------------------------------------------------------------------------------
# Numbers.
# ---------------------------------------------------------------------------------------------
def percentile(values: list[float], fraction: float) -> float | None:
    """Nearest-rank: the smallest value with at least `fraction` of the sample at or below it. With
    n=24 the p95 is the 23rd value, i.e. the second-worst measurement: one outlier moves it."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(fraction * len(ordered)) - 1)]


def describe(values: list[float]) -> dict:
    values = [v for v in values if v is not None]
    if not values:
        return {"n": 0}
    return {
        "n": len(values),
        "mean": sum(values) / len(values),
        "p50": percentile(values, 0.50),
        "p95": percentile(values, 0.95),
        "min": min(values),
        "max": max(values),
    }


def _latency(record: dict, name: str) -> float | None:
    return (record.get("latency_s") or {}).get(name)


def stage_of(record: dict) -> str:
    return (record.get("labels") or {}).get("stage", "")


def latency_report(records: list[dict]) -> dict:
    return {
        name: describe([_latency(r, name) for r in records])
        for name in (
            "total",
            "first_event",
            "first_message",
            "first_text_delta",
            "final_answer_first_delta",
            "launch_overhead",
            "python_startup",
        )
    }


def cost_report(records: list[dict]) -> dict:
    priced = [r for r in records if r.get("cost_usd") is not None]
    tokens = [(r.get("usage") or {}).get("total_tokens") for r in records]
    return {
        "cost_usd": describe([r["cost_usd"] for r in priced]),
        "total_tokens": describe(tokens),
        "context_tokens_peak": describe(
            [(r.get("usage") or {}).get("context_tokens_peak") for r in records]
        ),
        "tool_calls": describe([len(r.get("tool_calls") or []) for r in records]),
        "unpriced_invocations": len(records) - len(priced),
    }


def cache_report(records: list[dict]) -> dict:
    """How much of what the puntal read came out of the prompt cache. A click after the cache's
    five-minute life pays the creation price again, so this is the number that moves the cost."""
    read = sum((r.get("usage") or {}).get("cache_read_input_tokens") or 0 for r in records)
    created = sum((r.get("usage") or {}).get("cache_creation_input_tokens") or 0 for r in records)
    fresh = sum((r.get("usage") or {}).get("input_tokens") or 0 for r in records)
    total = read + created + fresh
    return {
        "cache_read": read,
        "cache_creation": created,
        "uncached_input": fresh,
        "read_fraction": (read / total) if total else None,
    }


def by_action(records: list[dict]) -> dict[str, dict]:
    grouped: dict[str, list[dict]] = {}
    for record in records:
        grouped.setdefault(record.get("action", "?"), []).append(record)
    return {
        action: {
            "n": len(group),
            "total": describe([_latency(r, "total") for r in group]),
            "first_text_delta": describe([_latency(r, "first_text_delta") for r in group]),
            "cost_usd": describe([r["cost_usd"] for r in group if r.get("cost_usd") is not None]),
            "total_tokens": describe([(r.get("usage") or {}).get("total_tokens") for r in group]),
            "tool_calls": describe([len(r.get("tool_calls") or []) for r in group]),
        }
        for action, group in sorted(grouped.items())
    }


def outcomes(records: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        counts[record.get("outcome", "?")] = counts.get(record.get("outcome", "?"), 0) + 1
    return counts


def path_report(records: list[dict]) -> dict:
    """How the invocations were answered: on which path (a schema-1 record, which has none, was the
    tool loop), how many needed a retry turn, and how many the executor refused at least once."""
    paths: dict[str, int] = {}
    for record in records:
        paths[record.get("path", "slow")] = paths.get(record.get("path", "slow"), 0) + 1
    plans = [r.get("plan") or {} for r in records]
    return {
        "paths": paths,
        "retried": sum(1 for plan in plans if plan.get("retries")),
        "executor_refusals": sum(
            1
            for plan in plans
            if any(a.get("stage") == "executor" for a in plan.get("attempts", []))
        ),
    }


# ---------------------------------------------------------------------------------------------
# Coherence.
# ---------------------------------------------------------------------------------------------
@dataclass
class Contradiction:
    """One thing the bench found wrong, with enough evidence to check it without rerunning."""

    kind: str
    code: str
    message: str
    seq: int | None = None
    session: str = ""
    action: str = ""
    invocation_id: str = ""
    occurrences: int = 1

    def line(self) -> str:
        where = f"seq {self.seq} {self.session} {self.action}".strip() if self.seq else "store"
        more = f" (and {self.occurrences - 1} more)" if self.occurrences > 1 else ""
        return f"[{self.kind}/{self.code}] {where}: {self.message}{more}"


@dataclass
class CoherenceReport:
    contradictions: list[Contradiction] = field(default_factory=list)
    contract_violations: list[Contradiction] = field(default_factory=list)
    gap_notes_expected: int = 0
    gap_notes_found: int = 0
    gap_notes_unexpected: list[Contradiction] = field(default_factory=list)
    gap_notes_missing: list[Contradiction] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    invocations_checked: int = 0
    sessions: list[str] = field(default_factory=list)


READS = ("show_board", "board_report")


class Replay:
    """Walks a trace in order, holding the three oracles' state, and collects what they find.

    - the INVARIANTS hold for any store, whoever wrote it (ids sequential, the derived summary equal
      to a recount, statuses and resolutions consistent);
    - the ONE-STEP oracle applies each action's rules to the store as it was before the invocation
      and compares: it blames the invocation that introduced a defect, and only that one;
    - the LEDGER replays every action that succeeded from the empty store, independent of what the
      store says, and is compared with the store at every session boundary: it catches a fact
      established in session N that is no longer true in session N+1, and a response in N+1 that
      reports a fact differently from how N established it.
    """

    def __init__(self, telemetry: dict[str, dict]) -> None:
        self.telemetry = telemetry
        self.report = CoherenceReport()
        self.ledger = domain.empty_state()
        self.previous_after: dict | None = None
        self.invariants_seen: dict[tuple[str, str], Contradiction] = {}
        self.sessions_with_a_read: set[str] = set()

    def run(self, trace: list[dict]) -> CoherenceReport:
        for record in sorted(trace, key=lambda r: r["seq"]):
            if not record["action"].startswith("calibrate"):
                self.check(record)
        self.report.contradictions.extend(self.invariants_seen.values())
        return self.report

    def found(self, kind: str, violation: domain.Violation, record: dict) -> None:
        self.report.contradictions.append(
            self.contradiction(kind, violation.code, violation.message, record)
        )

    @staticmethod
    def contradiction(kind: str, code: str, message: str, record: dict) -> Contradiction:
        return Contradiction(
            kind,
            code,
            message,
            record["seq"],
            record.get("session", ""),
            record["action"],
            record["invocation_id"],
        )

    def check(self, record: dict) -> None:
        report = self.report
        action, session = record["action"], record.get("session", "")
        before, after = record["store_before"], record["store_after"]
        payload = record.get("payload") or {}
        telemetry = self.telemetry.get(record["invocation_id"])
        succeeded = telemetry is not None and telemetry.get("outcome") == "ok"
        report.invocations_checked += 1
        if session not in report.sessions:
            report.sessions.append(session)
            if self.previous_after is not None:
                # A session boundary: every fact the earlier sessions established must still be there.
                for violation in domain.diff_states(self.ledger, before):
                    self.found("cross_session", violation, record)
        self.check_continuity(record, before)
        for violation in domain.check_invariants(after):
            known = self.invariants_seen.get(violation.key())
            if known is not None:
                known.occurrences += 1
            else:
                self.invariants_seen[violation.key()] = self.contradiction(
                    "invariant", violation.code, violation.message, record
                )
        expected_after, _ = domain.apply_action(before, action, payload)
        for violation in domain.diff_states(expected_after, after):
            self.found("state_divergence", violation, record)
        if telemetry is None:
            report.contradictions.append(
                self.contradiction(
                    "harness",
                    "no_telemetry",
                    "the driver left no telemetry line for this invocation",
                    record,
                )
            )
        else:
            self.check_telemetry(record, telemetry, succeeded)
        # The ledger moves only on a success; after a failed run it is re-synced to the store, so one
        # failure is reported once and not as a divergence at every later boundary.
        self.ledger = (
            domain.apply_action(self.ledger, action, payload)[0]
            if succeeded
            else copy.deepcopy(after)
        )
        self.previous_after = after

    def check_continuity(self, record: dict, before: dict) -> None:
        if self.previous_after is None:
            if before != domain.empty_state():
                self.report.notes.append(
                    f"seq {record['seq']}: the first invocation started on a store that was not empty"
                )
        elif before != self.previous_after:
            differences = domain.diff_states(self.previous_after, before) or [
                domain.Violation(
                    "store_changed", "the store differs from how the previous invocation left it"
                )
            ]
            for violation in differences:
                self.found("store_changed_outside_invocation", violation, record)

    def check_telemetry(self, record: dict, telemetry: dict, succeeded: bool) -> None:
        report = self.report
        action, session = record["action"], record.get("session", "")
        payload = record.get("payload") or {}
        if succeeded:
            response = telemetry.get("response", "")
            for violation in domain.check_response_text(
                action, payload, response, record["store_before"], record["store_after"]
            ):
                self.found("response", violation, record)
            if (
                action in READS
                and session not in self.sessions_with_a_read
                and report.sessions.index(session) >= 1
            ):
                # The first look at the board in a later session must show what the earlier
                # sessions established, whatever the store says.
                for violation in domain.check_response_text(
                    action, payload, response, self.ledger, self.ledger
                ):
                    self.found("cross_session", violation, record)
        if action in READS:
            self.sessions_with_a_read.add(session)
        for reason in telemetry.get("tool_violations") or []:
            report.contract_violations.append(
                self.contradiction("contract", "tool_violation", reason, record)
            )
        has_gap_note = bool(telemetry.get("gap_note"))
        if action in domain.GAP_ACTIONS:
            report.gap_notes_expected += 1
            if has_gap_note:
                report.gap_notes_found += 1
            elif succeeded:
                report.gap_notes_missing.append(
                    self.contradiction(
                        "gap_note",
                        "missing",
                        "the node is silent on this action and no GAP note was left",
                        record,
                    )
                )
        elif has_gap_note:
            report.gap_notes_unexpected.append(
                self.contradiction(
                    "gap_note",
                    "unexpected",
                    f"a GAP note on an action its node describes: {telemetry['gap_note']!r}",
                    record,
                )
            )


def analyze_coherence(trace: list[dict], telemetry: dict[str, dict]) -> CoherenceReport:
    """Replays the trace against the rules of `domain.py`; see `Replay` for what is checked."""
    return Replay(telemetry).run(trace)
