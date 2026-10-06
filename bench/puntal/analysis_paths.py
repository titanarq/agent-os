"""Which path answered each invocation (the fast plan or the slow tool loop), for the bench's summary."""

from __future__ import annotations


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
