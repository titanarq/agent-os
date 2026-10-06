"""What one model turn of an invocation left behind: the raw material of its telemetry."""

from __future__ import annotations

import dataclasses

from agent_os.product.puntal.stream.launch import BackendRun
from agent_os.product.puntal.stream.observer import StreamObserver


@dataclasses.dataclass
class TurnRun:
    # `plan` (the first turn), `retry` (after a rejected plan) or `slow` (the tool loop).
    kind: str
    observer: StreamObserver
    run: BackendRun
    flags: list[str]
    contract_text: str
    started_s: float
    ended_s: float
    scratch_extra: list[str]
    # Set by the invocation once it has judged this turn: `ok`, or why it was not.
    outcome: str = "ok"
    outcome_detail: str = ""
