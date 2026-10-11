"""Writes down a quota refusal the worker driver itself read, as the backend's quota verdict.

The guard persists the verdict (`.cache/agent_guard_<backend>.json`, `last_quota_status`) from a
live worker's tick and from the logs role runs leave. A worker relaunched into an exhausted window
dies before a tick sees it, and `worker_task.sh stage-exit` is the only reader of its refusal:
without this, the next launch -- the planner's, a validator's, a relaunch -- read a stale
`allowed` and ran into the same wall to find out again.

    python -m agent_os.product.tracker.quota_verdict exhausted --backend claude

Only a refusal is recorded; a run that saw no quota signal is no evidence the window is open. The
verdict ages out by its own TTL at the reader (`agent_lib.read_persisted_quota_verdict`), so a
record made now stops counting once the window has had time to reopen. Never fails the caller:
the cut is already decided, and a verdict that could not be written only costs a later probe.
"""

from __future__ import annotations

import argparse
import time

from agent_os.guard import record_quota_observation


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m agent_os.product.tracker.quota_verdict")
    parser.add_argument("status", choices=["exhausted"])
    parser.add_argument("--backend", required=True)
    arguments = parser.parse_args()
    line = record_quota_observation(
        arguments.backend, arguments.status, time.time_ns(), source="the worker's stage exit"
    )
    if line:
        print(line)


if __name__ == "__main__":
    main()
