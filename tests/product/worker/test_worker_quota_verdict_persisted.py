"""A quota cut the driver itself reads is written down as the backend's quota verdict (stage1k, G).

The guard persists the verdict (`.cache/agent_guard_<backend>.json`, `last_quota_status`) while a
worker is alive and from the logs role runs leave. A worker relaunched into an exhausted window dies
before the guard's tick ever sees its stream: `stage-exit` reads the refusal and cuts the run as
`reason=quota`, and nothing recorded it. The next launch -- the planner's own, a validator's, a
relaunch -- then read a stale `allowed` and ran into the same wall to find out again. The verdict
ages out by its own TTL (`read_persisted_quota_verdict`, `role_launch_plan`), which is how it stops
holding once the window reopens.
"""

from __future__ import annotations

import json
import os
import time

import pytest
from test_worker_quota_refusal_cut import (
    REJECTED_RATE_LIMIT_EVENT,
    SESSION_LIMIT_LINE,
    _stage_exit,
)

from agent_os import lib as agent_lib


def verdict_after_a_stage_exit(tmp_path, **stage_exit_arguments):
    _stage_exit(tmp_path, **stage_exit_arguments)
    return agent_lib.read_persisted_quota_verdict("claude", cache_dir=tmp_path / "cache")


def test_a_quota_refusal_the_driver_read_is_persisted_as_exhausted_and_fresh(tmp_path):
    verdict = verdict_after_a_stage_exit(
        tmp_path, events_text="", log_text=f"{SESSION_LIMIT_LINE}\n", backend_status=1
    )
    assert verdict.status == "exhausted", verdict.reason
    assert verdict.age_seconds is not None and verdict.age_seconds < 60


def test_a_rejected_rate_limit_event_in_the_stream_is_persisted_too(tmp_path):
    verdict = verdict_after_a_stage_exit(
        tmp_path, events_text=f"{REJECTED_RATE_LIMIT_EVENT}\n", log_text="", backend_status=1
    )
    assert verdict.status == "exhausted", verdict.reason


def test_a_stage_exit_that_saw_no_quota_signal_writes_no_verdict(tmp_path):
    """Only what was observed is recorded: a clean exit is no evidence the window is open."""
    verdict = verdict_after_a_stage_exit(
        tmp_path,
        events_text=json.dumps({"type": "system", "subtype": "init"}) + "\n",
        log_text="",
        backend_status=0,
    )
    assert verdict.status == "unknown", verdict.reason


def test_the_persisted_verdict_keeps_the_stall_bookkeeping_it_was_written_beside(tmp_path):
    """The verdict file is the guard's own bookkeeping file: recording one field of it must not
    reset the rest, and the file stays valid JSON the guard reads back."""
    verdict = verdict_after_a_stage_exit(
        tmp_path, events_text="", log_text=f"{SESSION_LIMIT_LINE}\n", backend_status=1
    )
    recorded = json.loads(verdict.source.read_text())
    assert recorded["last_quota_status"] == "exhausted"
    assert set(recorded) > {"last_quota_status"}, recorded


@pytest.mark.parametrize("hours_old", [6])
def test_an_old_persisted_exhausted_reads_as_stale_to_the_launch_plan(tmp_path, hours_old):
    """The window reopens on its own schedule and nothing observes that, so the launch decides on
    the verdict's age: this is what makes a persisted `exhausted` expire."""
    verdict = verdict_after_a_stage_exit(
        tmp_path, events_text="", log_text=f"{SESSION_LIMIT_LINE}\n", backend_status=1
    )
    then = time.time() - hours_old * 3600
    os.utime(verdict.source, (then, then))
    aged = agent_lib.read_persisted_quota_verdict("claude", cache_dir=tmp_path / "cache")
    assert aged.status == "exhausted"
    assert aged.age_seconds is not None and aged.age_seconds > hours_old * 3600 - 60
