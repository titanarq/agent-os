"""The four-hour clock: is the whole suite due, given the age of the last successful full run."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

NEVER = "never"
UNKNOWN = "unknown"


@dataclass(frozen=True)
class FullRunClock:
    due: bool
    reason: str


def parse_last_full_run(text: str) -> datetime | None:
    """`never` and `unknown` are `None`: both make a full run due. Anything else must be an
    ISO 8601 instant carrying its timezone, because comparing it with a naive one is a guess."""
    stripped = text.strip()
    if stripped in (NEVER, UNKNOWN):
        return None
    try:
        parsed = datetime.fromisoformat(stripped)
    except ValueError as error:
        raise ValueError(
            f"--last-full-run must be ISO 8601, `{NEVER}` or `{UNKNOWN}`, not {text!r}"
        ) from error
    if parsed.tzinfo is None:
        raise ValueError(f"--last-full-run {text!r} carries no timezone")
    return parsed


def _describe_age(age: timedelta) -> str:
    total_minutes = int(age.total_seconds() // 60)
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours} h {minutes:02d} min"


def full_run_is_due(
    last_full_run: datetime | None, now: datetime, interval_hours: float
) -> FullRunClock:
    if last_full_run is None:
        return FullRunClock(True, "no full run is recorded (never)")
    age = now - last_full_run
    interval = timedelta(hours=interval_hours)
    reason = (
        f"last full run {last_full_run.isoformat()} is {_describe_age(age)} old "
        f"(interval {interval_hours:g} h)"
    )
    return FullRunClock(age >= interval, reason)
