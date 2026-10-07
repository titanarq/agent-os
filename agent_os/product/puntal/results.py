"""What an invocation ends with."""

from __future__ import annotations

import dataclasses
import pathlib

from agent_os.product.puntal.fast.operations import Plan
from agent_os.product.puntal.telemetry.record import InvocationTrace


@dataclasses.dataclass
class InvocationResult:
    trace: InvocationTrace
    log_path: pathlib.Path
    # What the app is told (empty unless the invocation was answered), and the exit status.
    answer: str
    status: int
    # The plan as the model sent it: operations and answer with their `{{placeholders}}` unfilled.
    plan: Plan | None
    bindings: dict
    applied: bool


@dataclasses.dataclass
class Finish:
    """How the loop ended: the outcome and everything the caller and the telemetry need of it."""

    outcome: str
    detail: str = ""
    plan: Plan | None = None
    answer: str = ""
    gap: str | None = None
    bindings: dict = dataclasses.field(default_factory=dict)
    applied: bool = False
