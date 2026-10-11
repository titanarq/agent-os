"""A plan under the clock: a due full run wins over the selection, a push may run nothing."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from agent_os.product.test_selection.clock.full_run_clock import (
    UNKNOWN,
    FullRunClock,
    full_run_is_due,
    parse_last_full_run,
)
from agent_os.product.test_selection.plan import TestPlan


def plan_under_clock(
    last_full_run_text: str | None,
    interval_hours: float,
    only_when_due: bool,
    now: datetime,
    selection: Callable[[], TestPlan],
) -> TestPlan:
    """Without `last_full_run_text` the clock is not consulted: a local run never carries it."""
    if last_full_run_text is None:
        return selection()
    last_full_run = parse_last_full_run(last_full_run_text)
    clock = full_run_is_due(last_full_run, now, interval_hours)
    if last_full_run_text.strip() == UNKNOWN:
        clock = FullRunClock(True, "the last full run could not be read")
    if clock.due:
        return TestPlan("full", clock.reason)
    if only_when_due:
        return TestPlan("none", f"no full run is due: {clock.reason}")
    return selection()
