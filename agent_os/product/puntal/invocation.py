"""One invocation, end to end: pre-helper, the plan turn, the executor, and the escapes.

    pre-helper (code) -> plan turn (no tools) -> validate -> executor (code) -> answer
                              |                      |            |
                              | needs_state          | invalid    | refused
                              v                      v            v
                         slow turn (tools)       retry turn   retry turn

At most ONE retry (a rejected plan, or an executor that refused it) and ONE slow turn, whichever
order they come in: the slow turn answers for itself, so nothing follows it. Ceilings bind the
invocation, so a later turn is run with what the earlier ones left.
"""

from __future__ import annotations

import os
import shlex
from datetime import UTC, datetime

from agent_os.lib import write_role_run_exit_marker
from agent_os.product.puntal.constants import (
    MAX_RETRIES,
    OUTCOME_EXIT_STATUS,
    PATH_FAST,
    PATH_SLOW,
    PUNTAL_ROLE,
)
from agent_os.product.puntal.fast.actor import actor_of, command_environment
from agent_os.product.puntal.fast.brief import (
    build_brief,
    previous_attempt_section,
    rejected_plan_section,
    slow_path_section,
)
from agent_os.product.puntal.fast.executor import (
    ExecutorVerdict,
    resolve_executor_command,
    run_executor,
)
from agent_os.product.puntal.fast.operations import (
    Plan,
    fill_bindings,
    parse_plan,
    render_answer,
    validate_plan,
)
from agent_os.product.puntal.fast.pre_helper import LoadedState, load_declared_state
from agent_os.product.puntal.options import Options, Request
from agent_os.product.puntal.results import Finish, InvocationResult
from agent_os.product.puntal.stream.audit import split_gap_note
from agent_os.product.puntal.stream.events import Ceilings
from agent_os.product.puntal.stream.launch import Clock
from agent_os.product.puntal.stream.turn_run import TurnRun
from agent_os.product.puntal.telemetry.outcome import classify_turn
from agent_os.product.puntal.telemetry.record import InvocationTrace
from agent_os.product.puntal.turn import remaining_ceilings, run_turn

ATTEMPT_TEXT_CHARS = 2000


class InvocationRun:
    """The state of one invocation as its turns happen. A class, not a function with a dozen locals:
    each step below reads and writes what the earlier ones left."""

    def __init__(self, request: Request, options: Options, clock: Clock, log) -> None:
        self.request, self.options, self.clock, self.log = request, options, clock, log
        self.actor = actor_of(request.actor)
        self.turns: list[TurnRun] = []
        self.kind = "slow" if options.path == PATH_SLOW else "plan"
        self.slow_path_reason: str | None = "forced by --path slow" if self.kind == "slow" else None
        self.extra_sections: tuple[tuple[str, str], ...] = (
            (previous_attempt_section(request.previous_attempt),)
            if request.previous_attempt
            else ()
        )
        self.retries = 0
        self.attempts: list[dict] = []
        self.loaded: LoadedState | None = None
        self.pre_helper_s: float | None = None
        self.executor_s: float | None = None
        self.executor_row: dict = {"ran": False, "ok": None, "crashed": None, "errors": []}
        self.spawned_at_s: float | None = None

    # -- steps ---------------------------------------------------------------------------------
    def load_state(self) -> None:
        if not self.request.declared_reads:
            return
        started = self.clock.now()
        self.loaded = load_declared_state(
            self.request.declared_reads,
            payload_text=self.request.payload,
            persistence_command=shlex.split(self.options.persistence_command),
            allowed_subcommands=self.options.read_subcommands,
            host_root=self.options.host_root,
            timeout_seconds=self.options.ceilings.timeout_seconds,
            environment=command_environment(self.actor),
        )
        self.pre_helper_s = self.clock.now() - started

    def brief(self) -> str:
        loaded_text = self.loaded.text if self.loaded else None
        if loaded_text is None and self.options.path == PATH_FAST:
            loaded_text = ""
        return build_brief(
            node_slice=self.request.node_slice,
            action=self.request.action,
            payload=self.request.payload,
            relevant_state=self.request.relevant_state,
            loaded_state=loaded_text,
            extra_sections=self.extra_sections,
        )

    def take_turn(self, ceilings: Ceilings) -> TurnRun:
        on_slow_path = self.kind == "slow"
        if self.spawned_at_s is None:
            self.spawned_at_s = self.clock.now()
        turn = run_turn(
            kind=self.kind,
            options=self.options,
            clock=self.clock,
            ceilings=ceilings,
            contract=self.options.slow_contract if on_slow_path else self.options.fast_contract,
            brief=self.brief(),
            with_state_tool=on_slow_path,
            log=self.log,
            actor=self.actor,
        )
        turn.outcome, turn.outcome_detail = classify_turn(turn.run, turn.observer)
        self.turns.append(turn)
        return turn

    def execute(self, plan: Plan) -> ExecutorVerdict:
        started = self.clock.now()
        verdict = run_executor(
            resolve_executor_command(self.options.executor_command, self.options.host_root),
            plan.operations,
            timeout_seconds=self.options.executor_timeout_seconds,
            environment=command_environment(self.actor),
        )
        self.executor_s = self.clock.now() - started
        self.executor_row = {
            "ran": True,
            "ok": verdict.ok,
            "crashed": verdict.crashed,
            "errors": verdict.errors,
        }
        return verdict

    def reject(self, text: str, errors: list[str], *, stage: str) -> bool:
        """Records a rejected attempt and prepares the retry turn. False when none is left."""
        self.attempts.append(
            {
                "turn": len(self.turns),
                "stage": stage,
                "errors": errors,
                "text": text[:ATTEMPT_TEXT_CHARS],
            }
        )
        if self.retries >= MAX_RETRIES:
            return False
        self.retries += 1
        self.kind = "retry"
        self.extra_sections = (rejected_plan_section(text, errors),)
        return True

    def go_slow(self, reason: str) -> None:
        self.kind = "slow"
        self.slow_path_reason = reason
        self.extra_sections = (slow_path_section(reason),)

    # -- the loop ------------------------------------------------------------------------------
    def run(self) -> Finish:
        self.load_state()
        ceilings: Ceilings | None = self.options.ceilings
        while True:
            if ceilings is None:
                return Finish("ceiling_cut", "earlier turns spent the invocation's ceilings")
            turn = self.take_turn(ceilings)
            if turn.outcome != "ok":
                return Finish(turn.outcome, turn.outcome_detail)
            text = turn.observer.final_text()
            if self.kind == "slow":
                answer, gap = split_gap_note(text)
                return Finish("ok", answer=answer, gap=gap)
            ceilings = remaining_ceilings(self.options.ceilings, self.turns)
            plan, errors = parse_plan(text)
            if plan is not None:
                errors = validate_plan(plan)
            if errors:
                if not self.reject(text, errors, stage="validation"):
                    return Finish("invalid_plan", "; ".join(errors)[:400], plan)
                continue
            if plan.asks_for_state:
                self.go_slow(plan.needs_state)
                continue
            gap = plan.gap
            if self.options.plan_only:
                return Finish("ok", plan=plan, answer=render_answer(plan.answer), gap=gap)
            verdict = self.execute(plan)
            if verdict.crashed:
                return Finish("executor_failed", "; ".join(verdict.errors)[:400], plan, gap=gap)
            if not verdict.ok:
                if not self.reject(text, verdict.errors, stage="executor"):
                    return Finish("executor_failed", "; ".join(verdict.errors)[:400], plan, gap=gap)
                continue
            try:
                answer = render_answer(fill_bindings(plan.answer, verdict.bindings))
            except KeyError as error:
                detail = f"the executor did not return a binding the answer needs: {error.args[0]}"
                return Finish(
                    "executor_failed",
                    detail,
                    plan,
                    gap=gap,
                    bindings=verdict.bindings,
                    applied=True,
                )
            return Finish(
                "ok", plan=plan, answer=answer, gap=gap, bindings=verdict.bindings, applied=True
            )

    def trace(self, started_at: datetime, finish: Finish) -> InvocationTrace:
        reads, plan = self.loaded, finish.plan
        return InvocationTrace(
            started_at=started_at,
            turns=self.turns,
            path=PATH_SLOW if self.kind == "slow" or self.options.path == PATH_SLOW else PATH_FAST,
            slow_path_reason=self.slow_path_reason,
            outcome=finish.outcome,
            outcome_detail=finish.detail,
            response=finish.answer if finish.outcome == "ok" else "",
            gap_note=finish.gap if isinstance(finish.gap, str) else None,
            declared_reads={
                "declared": self.request.declared_reads,
                "ran": reads.ran if reads else 0,
                "failed": reads.failed if reads else 0,
                "problems": [
                    *self.request.declaration_problems,
                    *(reads.problems if reads else []),
                ],
            },
            plan={
                "operations": len(plan.operations)
                if plan and isinstance(plan.operations, list)
                else None,
                "applied": finish.applied,
                "retries": self.retries,
                "attempts": self.attempts,
                "bindings": finish.bindings,
            },
            executor=self.executor_row,
            pre_helper_s=self.pre_helper_s,
            executor_s=self.executor_s,
            answered_at_s=self.clock.now(),
            spawned_at_s=self.spawned_at_s,
        )


def invoke(request: Request, options: Options, clock: Clock) -> InvocationResult:
    """Runs one puntal. Writes the run's log and its exit marker; the telemetry line and the
    `runs.tsv` row are the post-helpers' (`postprocess.py`), after the caller has its answer."""
    started_at = datetime.now(UTC)
    options.run_dir.mkdir(parents=True, exist_ok=True)
    stamp = started_at.strftime("%Y%m%dT%H%M%S") + f"-{started_at.microsecond:06d}-{os.getpid()}"
    log_path = options.run_dir / f"{stamp}.log"
    with log_path.open("x", encoding="utf-8") as log:
        log.write(
            f"ts:        {stamp}\n"
            f"role:      {PUNTAL_ROLE} (class {options.class_name})\n"
            f"backend:   {options.backend}\n"
            f"model:     {options.model}\n"
            f"action:    {request.action}\n"
            f"node:      {request.node_id}\n"
            f"session:   {request.session_id or '(none)'}\n"
            f"invocation: {request.invocation_id}\n"
        )
        log.flush()
        run = InvocationRun(request, options, clock, log)
        finish = run.run()
    # The moment the backend returned, the way every role's driver marks it: the guard dates this
    # run's quota observation by it.
    write_role_run_exit_marker(log_path)
    answered = finish.outcome == "ok"
    return InvocationResult(
        trace=run.trace(started_at, finish),
        log_path=log_path,
        answer=finish.answer if answered else "",
        status=OUTCOME_EXIT_STATUS[finish.outcome],
        plan=finish.plan,
        bindings=finish.bindings,
        applied=finish.applied,
    )
