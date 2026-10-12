"""The rounds ledger: one line per round in `.cache/integrator/rounds.jsonl`, and the report read from it.

The judge's verdicts are recorded from day one with the outcome that came from outside (the CI), so a
change to the rules or the prompt is judged by evidence (the ADR, "Evidence")."""

from __future__ import annotations

import json
import pathlib
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime

LEDGER_RELATIVE_PATH = pathlib.Path(".cache") / "integrator" / "rounds.jsonl"
OUTCOMES = ("landed", "evicted", "solo")
CI_RESULTS = ("passed", "test-failure", "infrastructure")


class LedgerError(RuntimeError):
    pass


@dataclass(frozen=True)
class RoundRecord:
    members: tuple[int, ...]
    outcome: str
    evicted: int | None = None
    reason: str = ""
    ci_result: str = ""
    ci_minutes: float | None = None
    approval_to_merge_minutes: float | None = None
    facts: dict | None = None
    judge: dict | None = None

    def as_json(self) -> dict:
        return {
            "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "members": list(self.members),
            "facts": self.facts,
            "judge": self.judge,
            "outcome": f"evicted #{self.evicted}" if self.outcome == "evicted" else self.outcome,
            "reason": self.reason,
            "ci_result": self.ci_result,
            "ci_minutes": self.ci_minutes,
            "approval_to_merge_minutes": self.approval_to_merge_minutes,
        }


def minutes_between(earlier_iso: str, later_iso: str) -> float:
    try:
        earlier, later = datetime.fromisoformat(earlier_iso), datetime.fromisoformat(later_iso)
        return round((later - earlier).total_seconds() / 60, 1)
    except ValueError as error:
        raise LedgerError(f"not an ISO 8601 time: {error}") from error


def append_round(repository: pathlib.Path, record: RoundRecord) -> pathlib.Path:
    if record.outcome not in OUTCOMES:
        raise LedgerError(f"the outcome must be one of {', '.join(OUTCOMES)}")
    if record.outcome == "evicted" and record.evicted not in record.members:
        raise LedgerError("an `evicted` round names the evicted member among its members")
    if record.outcome == "solo" and not record.reason:
        raise LedgerError("a `solo` round carries its reason")
    path = repository / LEDGER_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as ledger:
        ledger.write(json.dumps(record.as_json(), separators=(",", ":")) + "\n")
    return path


def read_rounds(repository: pathlib.Path) -> list[dict]:
    path = repository / LEDGER_RELATIVE_PATH
    if not path.is_file():
        raise LedgerError(f"no ledger at {path}: no round has been recorded yet")
    rounds = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rounds.append(json.loads(line))
        except ValueError as error:
            raise LedgerError(f"{path} line {number} is not JSON: {error}") from error
    return rounds


def _said_independent(round_record: dict) -> bool:
    groups = (round_record.get("judge") or {}).get("groups") or []
    return any(
        group.get("verdict") == "independent" and len(group.get("members", [])) >= 2
        for group in groups
    )


def _mean(values: list[float]) -> str:
    return f"{sum(values) / len(values):.1f}" if values else "n/a"


def _waits(rounds: list[dict]) -> list[float]:
    return [
        r["approval_to_merge_minutes"]
        for r in rounds
        if r["outcome"] == "landed" and r.get("approval_to_merge_minutes") is not None
    ]


def report(rounds: list[dict]) -> str:
    landed_rounds = [r for r in rounds if r["outcome"] == "landed"]
    landed_pull_requests = sum(len(r["members"]) for r in landed_rounds)
    ci_runs = [r for r in rounds if r.get("ci_minutes") is not None]
    per_run = f"{landed_pull_requests / len(ci_runs):.2f}" if ci_runs else "n/a"
    solo_reasons = Counter(r["reason"] for r in rounds if r["outcome"] == "solo")
    evicted_rounds = [r for r in rounds if r["outcome"].startswith("evicted")]
    couplings = [r for r in rounds if _said_independent(r) and r.get("ci_result") == "test-failure"]
    ci_mean = _mean([r["ci_minutes"] for r in ci_runs])
    return "\n".join(
        [
            f"rounds attempted: {len(rounds)}; landed: {len(landed_rounds)}; evicted: {len(evicted_rounds)}",
            f"PRs landed: {landed_pull_requests}; CI runs: {len(ci_runs)}; PRs landed per CI run: {per_run}",
            f"mean CI minutes: {ci_mean}; mean approval-to-merge minutes: {_mean(_waits(rounds))}",
            "solo reasons:" + ("" if solo_reasons else " none"),
            *(f"  {count} x {reason}" for reason, count in solo_reasons.most_common()),
            f"judged independent, CI red by a coupling: {len(couplings)}",
            *(f"  {' '.join(f'#{n}' for n in r['members'])} -> {r['outcome']}" for r in couplings),
        ]
    )
