"""One model turn: a backend process in a throwaway directory, its stream folded as it arrives."""

from __future__ import annotations

import dataclasses
import os
import pathlib
import shlex
import shutil
import tempfile

from agent_os.product.puntal.constants import BACKEND_ENVIRONMENT, SHIM_NAME
from agent_os.product.puntal.options import Options
from agent_os.product.puntal.stream.events import Ceilings
from agent_os.product.puntal.stream.launch import (
    BackendRun,
    Clock,
    backend_flags,
    run_backend,
    write_state_shim,
)
from agent_os.product.puntal.stream.observer import StreamObserver
from agent_os.product.puntal.stream.turn_run import TurnRun
from agent_os.product.puntal.telemetry.outcome import invocation_cost, turn_usage


def flags_for(options: Options, *, with_state_tool: bool) -> list[str]:
    return backend_flags(
        model=options.model,
        effort=options.effort,
        max_cost_usd=options.ceilings.max_cost_usd,
        with_state_tool=with_state_tool,
    )


def run_turn(
    *,
    kind: str,
    options: Options,
    clock: Clock,
    ceilings: Ceilings,
    contract: str,
    brief: str,
    with_state_tool: bool,
    log,
) -> TurnRun:
    """Runs the backend once. `with_state_tool` is the slow path's: the `./state` shim, the one Bash
    rule that lets it run, and an observer that audits every call. Without it the turn has no tool at
    all, and any call it makes is a contract violation."""
    flags = flags_for(options, with_state_tool=with_state_tool)
    argv = [options.executable, *flags, "--system-prompt", contract, brief]
    observer = StreamObserver(ceilings, tools_allowed=with_state_tool)
    scratch = pathlib.Path(
        tempfile.mkdtemp(prefix="agent-os-puntal-scratch.", dir=os.environ.get("TMPDIR"))
    )
    started_s = clock.now()
    try:
        if with_state_tool:
            write_state_shim(scratch, options.host_root, shlex.split(options.persistence_command))
        log.write(f"--- turn: {kind} ---\n")
        log.flush()
        try:
            run = run_backend(
                argv,
                cwd=scratch,
                environment={**os.environ, **BACKEND_ENVIRONMENT},
                observer=observer,
                clock=clock,
                log=log,
                timeout_seconds=ceilings.timeout_seconds,
            )
        except OSError as error:
            observer.non_event_lines.append(f"could not start {options.executable}: {error}")
            run = BackendRun(None, None, False)
        scratch_extra = sorted(entry.name for entry in scratch.iterdir() if entry.name != SHIM_NAME)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    return TurnRun(
        kind=kind,
        observer=observer,
        run=run,
        flags=flags,
        contract_text=contract,
        started_s=started_s,
        ended_s=clock.now(),
        scratch_extra=scratch_extra,
    )


def remaining_ceilings(ceilings: Ceilings, turns: list[TurnRun]) -> Ceilings | None:
    """What the invocation has left for its next turn, or None when it has nothing left: the
    ceilings bind the whole invocation, not each of its turns."""
    tokens = ceilings.max_total_tokens - sum(turn_usage(t.observer)["total_tokens"] for t in turns)
    dollars = ceilings.max_cost_usd - (invocation_cost(turns) or 0.0)
    if tokens <= 0 or dollars <= 0:
        return None
    return dataclasses.replace(ceilings, max_total_tokens=tokens, max_cost_usd=dollars)
