#!/usr/bin/env python3
"""The puntal spike's measurement: latency, cost and coherence of a headless agent answering UI
actions live, over a toy helpdesk whose state is a real JSON document store.

NOT a test and never collected by pytest. It is the ONLY place real `claude -p` calls are authorised
(`docs/AGENTOS_V2_PLAN.md`, Phase 0), and it is built so that they cannot happen by accident:

- a real call needs `--allow-real-calls`; without it, or with `--dry-run`, the stage runs against
  `fake_claude.py` and spends nothing;
- it refuses to run under pytest (`PYTEST_CURRENT_TEST`);
- every real call is first written to a persistent counter file, and the call that would be the
  `REAL_CALL_CAP + 1`-th is refused, whatever stage, workdir or checkout it comes from. The cap is
  the constant below, not a setting. A dry run never touches the counter.

STAGES -- run them in this order, looking at the output of each before spending on the next
(`.venv/bin/python bench/puntal/measure.py <stage> ...`: it imports the package and pyyaml):

    calibrate --dry-run             # 2 calls: the smallest prompt, cold then warm cache
    main --session 1 --dry-run      # 8 calls: the first session, on an empty store
    main --session 2                # ... the same store, a fresh process per call
    main --session 3
    reserve --count 2 --model M     # up to 4 adaptive probes (another model, effort...)
    summarize                       # numbers and coherence, from the raw files only
    status                          # how much of the cap is spent

(replace `--dry-run` by `--allow-real-calls` to spend). Calibration is 2 calls, the main stage 3
sessions of 8 = 24, the reserve at most 4: 30, which is the cap. Everything the stages write lives in
`--workdir` (default `.cache/puntal-bench/`): the store the sessions share, `telemetry.jsonl` (the
driver's record of each call), `trace.jsonl` (the harness's record: the action, its payload and the
whole store before and after) and the config it generated. `summarize` reads those two files and
nothing else, so it can be rerun, and diffed, at will.

The counter lives in `~/.cache/agent-os/puntal-bench-real-calls.json` so that it spans checkouts and
worktrees; `--counter-file` or `PUNTAL_BENCH_COUNTER_FILE` move it (a test does).
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import pathlib
import shlex
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import analysis
import domain
import yaml
from store import Store

from agent_os.lib import load_agents_config
from agent_os.product import puntal

REPO_ROOT = HERE.parents[1]
DRIVER = REPO_ROOT / "bin" / "puntal_task.sh"
EXAMPLE_CONFIG = REPO_ROOT / "config.example.yaml"
NODES_DIR = HERE / "nodes"
FAKE_BACKEND = HERE / "fake_claude.py"
PERSISTENCE_API = HERE / "persistence_api.txt"
STORE_CLI = HERE / "store.py"
EXECUTOR_CLI = HERE / "executor.py"

# THE cap on real invocations, across every run of this script on this machine. Calibration (2) + the
# main stage (3 sessions of 8) + the reserve (4). Changing it is a decision to spend more, and belongs
# in a reviewed commit.
REAL_CALL_CAP = 30
DEFAULT_MODEL = "claude-sonnet-5-5"
RESERVE_MAX_PER_RUN = 4
# A setup that fails systematically (a flag the CLI rejects, a login that expired, a quota wall) would
# burn the cap on failures: two failed invocations in a row stop a stage, one stops the calibration.
FAILURE_STREAK_LIMIT = 2

Step = tuple[str, dict]

# Three sessions over one store. Session 1 starts on an empty store and establishes facts; 2 and 3
# must find them, extend them and report them correctly. Each session mixes every action, the gap one
# (`export_csv`, whose node does not describe exporting) among them, and each carries requests the
# rules must refuse.
SESSIONS: dict[str, list[Step]] = {
    "s1": [
        (
            "create_ticket",
            {"title": "Printer on floor 2 jams on every duplex job", "priority": "high"},
        ),
        ("create_ticket", {"title": "Wifi drops in meeting room B", "priority": "normal"}),
        ("create_ticket", {"title": "Add a dark theme to the dashboard", "priority": "low"}),
        ("change_status", {"id": "T-1", "status": "in_progress"}),
        ("change_status", {"id": "T-2", "status": "resolved", "note": "Rebooted the access point"}),
        ("show_board", {}),
        ("board_report", {}),
        ("export_csv", {}),
    ],
    "s2": [
        ("show_board", {}),
        ("change_status", {"id": "T-1", "status": "resolved", "note": "Replaced the fuser unit"}),
        ("create_ticket", {"title": "Rotate the shared mailbox password", "priority": "high"}),
        ("change_status", {"id": "T-2", "status": "in_progress"}),
        ("change_status", {"id": "T-3", "status": "in_progress"}),
        ("change_status", {"id": "T-9", "status": "in_progress"}),
        ("board_report", {}),
        ("export_csv", {}),
    ],
    "s3": [
        ("board_report", {}),
        ("create_ticket", {"title": "Archive last year's invoices", "priority": "low"}),
        ("change_status", {"id": "T-4", "status": "in_progress"}),
        ("change_status", {"id": "T-1", "status": "in_progress"}),
        (
            "change_status",
            {"id": "T-3", "status": "resolved", "note": "Dark theme shipped behind a flag"},
        ),
        ("show_board", {}),
        ("export_csv", {}),
        ("board_report", {}),
    ],
}
SESSION_NUMBERS = {"1": "s1", "2": "s2", "3": "s3"}
# The calibration's two calls. The first carries the smallest brief and no tool call: the context
# floor, cold. The second, warm, makes ONE read through the persistence tool: it proves the tool is
# reachable and permitted before a session is spent finding out, and costs one tool round trip.
CALIBRATION_STEPS = (("calibrate", "calibration"), ("calibrate_tool", "calibration-tool"))
CALIBRATION_CALLS = len(CALIBRATION_STEPS)


class Refusal(SystemExit):
    """The script declining to run: always a message and a non-zero status, never a traceback."""

    def __init__(self, message: str) -> None:
        super().__init__(f"measure.py: refusing: {message}")


class CapReached(Refusal):
    pass


# ---------------------------------------------------------------------------------------------
# The cap on real calls.
# ---------------------------------------------------------------------------------------------
def default_counter_file() -> pathlib.Path:
    configured = os.environ.get("PUNTAL_BENCH_COUNTER_FILE")
    if configured:
        return pathlib.Path(configured)
    return pathlib.Path.home() / ".cache" / "agent-os" / "puntal-bench-real-calls.json"


def real_calls_used(counter_file: pathlib.Path) -> int:
    try:
        return len(json.loads(counter_file.read_text()).get("calls", []))
    except FileNotFoundError:
        return 0


def reserve_real_call(counter_file: pathlib.Path, *, stage: str, invocation_id: str) -> int:
    """Counts one real call BEFORE it is made, under a lock, and refuses the one past the cap. The
    count is written first so that a call which hangs, crashes or is interrupted is still counted:
    the cap bounds what was attempted, not what succeeded. Returns the number of calls used,
    including this one."""
    counter_file.parent.mkdir(parents=True, exist_ok=True)
    with counter_file.open("a+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        handle.seek(0)
        text = handle.read()
        data = json.loads(text) if text.strip() else {"calls": []}
        used = len(data["calls"])
        if used >= REAL_CALL_CAP:
            raise CapReached(
                f"{used} real calls are already counted in {counter_file} and the cap is "
                f"{REAL_CALL_CAP}, across every run"
            )
        data["calls"].append(
            {
                "n": used + 1,
                "at": datetime.now(UTC).isoformat(timespec="seconds"),
                "stage": stage,
                "invocation_id": invocation_id,
            }
        )
        handle.seek(0)
        handle.truncate()
        handle.write(json.dumps(data, indent=1) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return used + 1


# ---------------------------------------------------------------------------------------------
# The run context.
# ---------------------------------------------------------------------------------------------
class Context:
    def __init__(self, args: argparse.Namespace, *, mode: str) -> None:
        self.mode = mode
        self.workdir = pathlib.Path(args.workdir).resolve()
        self.store_dir = self.workdir / "store"
        self.telemetry_file = self.workdir / "telemetry.jsonl"
        self.trace_file = self.workdir / "trace.jsonl"
        self.config_file = self.workdir / "agents.yaml"
        self.cache_dir = self.workdir / "cache"
        self.model = args.model
        self.path = args.puntal_path
        self.effort = args.effort
        self.timeout = args.timeout
        self.fault = getattr(args, "fake_fault", "") or ""
        self.counter_file = (
            pathlib.Path(args.counter_file) if args.counter_file else default_counter_file()
        )
        self.class_overrides = parse_assignments(args.class_override)
        self.puntal_overrides = parse_assignments(args.puntal_override)
        self.pause_between_sessions = getattr(args, "pause_between_sessions", 0)
        self.failure_streak = 0

    def prepare(self) -> None:
        for directory in (self.workdir, self.cache_dir):
            directory.mkdir(parents=True, exist_ok=True)
        self.config_file.write_text(yaml.safe_dump(self.bench_config(), sort_keys=False))

    def bench_config(self) -> dict:
        """`config.example.yaml` with the puntal's own settings filled in for this bench: the
        persistence API text, and whatever `--class-override` / `--puntal-override` changed."""
        config = yaml.safe_load(EXAMPLE_CONFIG.read_text())
        config["puntal"]["persistence_api_file"] = os.path.relpath(PERSISTENCE_API, host_root())
        config["puntal"].update(self.puntal_overrides)
        config["classes"]["puntal"].update(self.class_overrides)
        return config

    def persistence_command(self) -> str:
        return shlex.join([sys.executable, str(STORE_CLI), "--dir", str(self.store_dir)])

    def executor_command(self) -> str:
        return shlex.join([sys.executable, str(EXECUTOR_CLI), "--dir", str(self.store_dir)])

    def environment(self) -> dict[str, str]:
        environment = dict(os.environ)
        environment.update(
            AGENTS_CONFIG_PATH=str(self.config_file),
            AGENT_CACHE_DIR=str(self.cache_dir),
            PUNTAL_PERSISTENCE_COMMAND=self.persistence_command(),
            PUNTAL_EXECUTOR_COMMAND=self.executor_command(),
        )
        if self.mode == "dry":
            environment.update(
                PUNTAL_CLAUDE_BIN=str(FAKE_BACKEND),
                FAKE_PUNTAL_STATE_DIR=str(self.workdir / "fake-state"),
                FAKE_PUNTAL_FAULT=self.fault,
            )
        return environment


def host_root() -> pathlib.Path:
    """The root the driver resolves as the host's, by the rule `bin/_python.sh` uses: the environment's
    answer, else the git checkout this directory sits in, else the directory above the package."""
    configured = os.environ.get("AGENT_OS_HOST_ROOT")
    if configured:
        return pathlib.Path(configured)
    toplevel = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    return pathlib.Path(toplevel) if toplevel else REPO_ROOT.parent


def parse_assignments(items: list[str]) -> dict:
    parsed: dict = {}
    for item in items:
        key, separator, value = item.partition("=")
        if not separator:
            raise Refusal(f"{item!r} is not KEY=VALUE")
        parsed[key] = yaml.safe_load(value)
    return parsed


def scrub_backend_overrides() -> list[str]:
    """A real run uses the `claude` the machine resolves, never a stand-in a dry run or a test left in
    the environment: every `PUNTAL_<BACKEND>_BIN` is removed from this process (and so from the
    driver's) and the names removed are returned, to be said out loud."""
    removed = [
        name
        for name in os.environ
        if (name.startswith("PUNTAL_") and name.endswith("_BIN")) or name.startswith("FAKE_PUNTAL_")
    ]
    for name in removed:
        del os.environ[name]
    return removed


def resolve_mode(args: argparse.Namespace) -> str:
    """`dry` (the fake backend) or `real`. Real needs the explicit flag and never happens under
    pytest -- the order matters: the cheapest, loudest refusal comes first."""
    if args.dry_run and args.allow_real_calls:
        raise Refusal("--dry-run and --allow-real-calls contradict each other")
    if args.dry_run:
        return "dry"
    if not args.allow_real_calls:
        raise Refusal("a real call needs --allow-real-calls (use --dry-run for the fake backend)")
    if os.environ.get("PYTEST_CURRENT_TEST"):
        raise Refusal("this script makes real calls and is never run under pytest")
    return "real"


# ---------------------------------------------------------------------------------------------
# Running one invocation.
# ---------------------------------------------------------------------------------------------
def read_json_lines(path: pathlib.Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def append_json_line(path: pathlib.Path, record: dict) -> None:
    with path.open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def telemetry_for(context: Context, invocation_id: str) -> dict | None:
    for record in reversed(read_json_lines(context.telemetry_file)):
        if record.get("invocation_id") == invocation_id:
            return record
    return None


def run_invocation(
    context: Context,
    *,
    stage: str,
    session: str,
    step: int,
    of: int,
    action: str,
    payload: dict,
    node: str,
) -> dict:
    store = Store(context.store_dir)
    invocation_id = str(uuid.uuid4())
    before = store.dump()
    if context.mode == "real":
        used = reserve_real_call(context.counter_file, stage=stage, invocation_id=invocation_id)
        print(f"  REAL CALL {used}/{REAL_CALL_CAP} -> {context.model}", flush=True)
    command = [
        "bash",
        str(DRIVER),
        "--action",
        action,
        "--node-file",
        str(NODES_DIR / f"{node}.md"),
        "--payload",
        json.dumps(payload),
        "--session-id",
        f"{stage}-{session}",
        "--invocation-id",
        invocation_id,
        "--label",
        f"stage={stage}",
        "--label",
        f"step={step}",
        "--model",
        context.model,
        "--telemetry-file",
        str(context.telemetry_file),
        "--path",
        context.path,
    ]
    if context.effort:
        command += ["--effort", context.effort]
    if context.timeout:
        command += ["--timeout", str(context.timeout)]
    started = time.monotonic()
    # The driver kills its own backend at its safety timeout; this one only guards the driver.
    allowance = (context.timeout or context.puntal_overrides.get("timeout_seconds", 90)) + 120
    try:
        completed = subprocess.run(
            command,
            env=context.environment(),
            capture_output=True,
            text=True,
            check=False,
            cwd=REPO_ROOT,
            timeout=allowance,
        )
    except subprocess.TimeoutExpired:
        completed = subprocess.CompletedProcess(
            command, 124, "", f"the driver did not return within {allowance}s"
        )
    wall = time.monotonic() - started
    after = store.dump()
    seq = len(read_json_lines(context.trace_file)) + 1
    trace = {
        "seq": seq,
        "invocation_id": invocation_id,
        "stage": stage,
        "session": session,
        "step": step,
        "action": action,
        "payload": payload,
        "node": node,
        "store_before": before,
        "store_after": after,
        "driver_exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr_tail": completed.stderr[-2000:],
        "wall_s": round(wall, 3),
    }
    append_json_line(context.trace_file, trace)
    tele = telemetry_for(context, invocation_id)
    succeeded = tele is not None and tele["outcome"] == "ok"
    context.failure_streak = 0 if succeeded else context.failure_streak + 1
    if tele is None:
        print(
            f"[{stage} {session} {step}/{of}] {action}: NO TELEMETRY (driver exit {completed.returncode}) {completed.stderr[-300:]}"
        )
    else:
        signal_s = tele["latency_s"].get("first_text_delta")
        cost = tele.get("cost_usd")
        print(
            f"[{stage} {session} {step}/{of}] {action:<14} {tele['outcome']:<9} "
            f"total {tele['latency_s']['total']:.1f}s  first-signal "
            f"{'-' if signal_s is None else f'{signal_s:.1f}s'}  cost "
            f"{'-' if cost is None else f'${cost:.4f}'}  tools {len(tele['tool_calls'])}",
            flush=True,
        )
    limit = 1 if stage == "calibration" else FAILURE_STREAK_LIMIT
    if context.failure_streak >= limit:
        reason = "no telemetry" if tele is None else f"{tele['outcome']}: {tele['outcome_detail']}"
        raise Refusal(
            f"stopping after {context.failure_streak} failed invocation(s) in a row, nothing further "
            f"is spent (last: {reason[:300]}). Read {context.telemetry_file}"
        )
    return trace


def preflight_backend(executable: str, flags: list[str]) -> str:
    """Free checks on the real CLI before a call is counted: `--help` must list every flag the driver
    will pass (a CLI that renamed one is found here and not by a failed call), and `--version` placed
    after the full flag set makes the CLI validate their values (it rejects an unknown
    `--permission-mode` choice before it prints). Only `--help` and `--version` are ever run.
    Returns the CLI's version line."""
    try:
        help_text = subprocess.run(
            [executable, "--help"], capture_output=True, text=True, check=False, timeout=60
        ).stdout
    except (OSError, subprocess.TimeoutExpired) as error:
        raise Refusal(f"cannot run `{executable} --help`: {error}") from error
    names = sorted({flag.split("=", 1)[0] for flag in flags if flag.startswith("-")})
    unknown = [name for name in names if name not in help_text]
    if unknown:
        raise Refusal(
            f"`{executable} --help` does not list {unknown}: this CLI is not the one the driver was written for"
        )
    checked = subprocess.run(
        [executable, *flags, "--system-prompt", "preflight", "--version"],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    if checked.returncode != 0:
        raise Refusal(
            f"the CLI rejects the driver's flags: {(checked.stderr or checked.stdout).strip()[:300]}"
        )
    return checked.stdout.strip()


def require_budget(context: Context, calls: int) -> None:
    """Refuses a stage that would not fit in what is left of the cap, before it starts: a session cut
    in half by the cap is a session nobody can compare."""
    if context.mode != "real":
        return
    used = real_calls_used(context.counter_file)
    if used + calls > REAL_CALL_CAP:
        raise CapReached(
            f"this stage needs {calls} real calls and only {REAL_CALL_CAP - used} of the cap of "
            f"{REAL_CALL_CAP} remain ({context.counter_file})"
        )
    print(
        f"REAL MODE: {calls} calls planned, {used} already spent of the cap of {REAL_CALL_CAP}",
        flush=True,
    )
    config = load_agents_config(context.config_file)
    executable = puntal.backend_executable_for(config.classes["puntal"].backend, config.project)
    flags = puntal.backend_flags(
        model=context.model,
        effort=context.effort,
        max_cost_usd=config.classes["puntal"].max_cost_usd,
        with_state_tool=context.path == "slow",
    )
    print(f"preflight ({executable}): {preflight_backend(executable, flags)}", flush=True)


# ---------------------------------------------------------------------------------------------
# Stages.
# ---------------------------------------------------------------------------------------------
def verify_calibration_tool(context: Context, trace: dict) -> None:
    """After the call that reads through the persistence tool: it must really have run. A tool the
    CLI denied, or never offered, would make every action of every session fail the same way, and
    the cap is for measuring, not for finding that out."""
    tele = telemetry_for(context, trace["invocation_id"])
    if tele is None:
        return  # run_invocation has already stopped the stage for a missing record
    calls = tele["tool_calls"]
    ran = [c for c in calls if c["violation"] is None and c["is_error"] is False]
    if ran and not tele["permission_denials"]:
        return
    raise Refusal(
        "the calibration's tool call did not run: "
        f"{len(calls)} call(s), {tele['permission_denials']} denied by the CLI, tools offered "
        f"{tele['init'].get('tools')}. The allow rule or --tools did not take effect; nothing further "
        "is spent. Read the run's log in the workdir's cache directory"
    )


def stage_calibrate(context: Context) -> None:
    done = sum(1 for r in read_json_lines(context.trace_file) if r["stage"] == "calibration")
    if done >= CALIBRATION_CALLS:
        raise Refusal("calibration already ran; its two calls are in trace.jsonl")
    require_budget(context, CALIBRATION_CALLS - done)
    for index, (action, node) in enumerate(CALIBRATION_STEPS[done:], start=done + 1):
        trace = run_invocation(
            context,
            stage="calibration",
            session="cal",
            step=index,
            of=CALIBRATION_CALLS,
            action=action,
            payload={},
            node=node,
        )
        if action == "calibrate_tool":
            verify_calibration_tool(context, trace)


def require_calibration(context: Context) -> None:
    """A real session is not started on a setup the calibration has not passed."""
    if context.mode != "real":
        return
    passed = [
        r
        for r in read_json_lines(context.trace_file)
        if r["stage"] == "calibration" and r["driver_exit_code"] == 0
    ]
    if len(passed) < CALIBRATION_CALLS:
        raise Refusal("run `calibrate` first: no real session starts before its two calls passed")


def stage_main(context: Context, which: str) -> None:
    chosen = ["s1", "s2", "s3"] if which == "all" else [SESSION_NUMBERS[which]]
    trace = [r for r in read_json_lines(context.trace_file) if r["stage"] == "main"]
    plans = []
    for session in chosen:
        done = {r["step"] for r in trace if r["session"] == session}
        todo = [i for i in range(1, len(SESSIONS[session]) + 1) if i not in done]
        if not todo:
            raise Refusal(f"session {session} is already complete in trace.jsonl")
        for earlier in list(SESSIONS)[: list(SESSIONS).index(session)]:
            finished = {r["step"] for r in trace if r["session"] == earlier}
            if len(finished) < len(SESSIONS[earlier]) and earlier not in chosen:
                raise Refusal(f"session {session} needs session {earlier} to be complete first")
        plans.append((session, todo))
    require_calibration(context)
    measured = [r for r in read_json_lines(context.trace_file) if r["stage"] != "calibration"]
    if not measured and Store(context.store_dir).dump() != domain.empty_state():
        raise Refusal(
            f"{context.store_dir} holds data but nothing was measured there: use a fresh --workdir"
        )
    require_budget(context, sum(len(todo) for _, todo in plans))
    for position, (session, todo) in enumerate(plans):
        if position and context.pause_between_sessions:
            print(f"pausing {context.pause_between_sessions}s between sessions", flush=True)
            time.sleep(context.pause_between_sessions)
        for step in todo:
            action, payload = SESSIONS[session][step - 1]
            run_invocation(
                context,
                stage="main",
                session=session,
                step=step,
                of=len(SESSIONS[session]),
                action=action,
                payload=payload,
                node=domain.NODE_FOR_ACTION[action],
            )


def probe_steps(store_dump: dict, first_index: int, count: int) -> list[Step]:
    """The reserve's probes, chosen from the store as it is NOW so that each is valid: look at the
    board, file a ticket, move the oldest open one along, report. Cycles every four."""
    steps: list[Step] = []
    simulated = store_dump
    for offset in range(count):
        kind = (first_index + offset) % 4
        if kind == 0:
            step: Step = ("show_board", {})
        elif kind == 1:
            step = (
                "create_ticket",
                {"title": f"Probe ticket {first_index + offset + 1}", "priority": "normal"},
            )
        elif kind == 2:
            tickets = domain.tickets_of(simulated)
            open_ids = [
                i for i in domain.sorted_ticket_ids(simulated) if tickets[i]["status"] == "open"
            ]
            moving = [
                i
                for i in domain.sorted_ticket_ids(simulated)
                if tickets[i]["status"] == "in_progress"
            ]
            if open_ids:
                step = ("change_status", {"id": open_ids[0], "status": "in_progress"})
            elif moving:
                step = (
                    "change_status",
                    {"id": moving[0], "status": "resolved", "note": "Probe: resolved"},
                )
            else:
                step = ("show_board", {})
        else:
            step = ("board_report", {})
        simulated = domain.apply_action(simulated, step[0], step[1])[0]
        steps.append(step)
    return steps


def stage_reserve(context: Context, count: int) -> None:
    trace = read_json_lines(context.trace_file)
    if not any(r["stage"] == "main" for r in trace):
        raise Refusal("the reserve probes the store the main stage built: run the main stage first")
    done = sum(1 for r in trace if r["stage"] == "reserve")
    steps = probe_steps(Store(context.store_dir).dump(), done, count)
    require_budget(context, len(steps))
    for index, (action, payload) in enumerate(steps, start=1):
        run_invocation(
            context,
            stage="reserve",
            session=f"probe{done // 4 + 1}",
            step=done + index,
            of=count,
            action=action,
            payload=payload,
            node=domain.NODE_FOR_ACTION[action],
        )


# ---------------------------------------------------------------------------------------------
# Summary.
# ---------------------------------------------------------------------------------------------
def fmt(value: float | None, unit: str = "s", places: int = 2) -> str:
    return "-" if value is None else f"{value:.{places}f}{unit}"


def stats_line(label: str, stats: dict, unit: str = "s", places: int = 2) -> str:
    if not stats.get("n"):
        return f"  {label:<34} no data"
    return (
        f"  {label:<34} n={stats['n']:<3} mean {fmt(stats['mean'], unit, places)}  p50 {fmt(stats['p50'], unit, places)}  "
        f"p95 {fmt(stats['p95'], unit, places)}  max {fmt(stats['max'], unit, places)}"
    )


def verdict(value: float | None, limit: float, *, label: str) -> str:
    if value is None:
        return f"  {label}: NO DATA"
    return f"  {label}: {'PASS' if value < limit else 'FAIL'}  ({value:.3f} against < {limit:g})"


def summarize(
    workdir: pathlib.Path, *, first_signal_max: float, p95_max: float, cost_mean_max: float
) -> tuple[str, dict]:
    telemetry = read_json_lines(workdir / "telemetry.jsonl")
    trace = read_json_lines(workdir / "trace.jsonl")
    by_id = {record["invocation_id"]: record for record in telemetry}
    calibration = [r for r in telemetry if analysis.stage_of(r) == "calibration"]
    main = [r for r in telemetry if analysis.stage_of(r) == "main"]
    reserve = [r for r in telemetry if analysis.stage_of(r) == "reserve"]
    coherence = analysis.analyze_coherence(
        [t for t in trace if t["stage"] in ("main", "reserve")], by_id
    )
    lines: list[str] = []
    out = lines.append
    out("PUNTAL SPIKE -- MEASUREMENT SUMMARY")
    out(
        f"computed from {workdir / 'telemetry.jsonl'} ({len(telemetry)} records) and trace.jsonl ({len(trace)} records)"
    )
    out("")
    out("READ THIS FIRST")
    out(
        f"  - Sample sizes: calibration {len(calibration)}, main {len(main)}, reserve {len(reserve)}. A p95 is the nearest-rank value: with n=24 it is"
    )
    out(
        "    the 23rd of 24 ordered measurements, so a single slow call moves it. Treat percentiles as an indication, not an estimate."
    )
    out(
        "  - cost_usd is the CLI's total_cost_usd. Under a subscription login it is NOTIONAL (API-equivalent), not money charged."
    )
    out(
        "  - Latencies are seconds from the moment puntal_task.sh was entered (the click reaching the driver) -- they include the"
    )
    out("    shell and Python start-up and the config load -- to the response being complete.")
    out(
        "  - TIME-TO-FIRST-SIGNAL is the first assistant text_delta of any message (what a UI could start showing); first_event is the"
    )
    out(
        "    first line of the stream (the CLI's init), first_message the first message_start, final_answer_first_delta the first delta of the"
    )
    out("    message that carries the answer (after the tool calls).")
    out("")
    out("CALIBRATION (the context floor: what a call carries before it has done anything)")
    if not calibration:
        out("  no calibration records")
    for record in calibration:
        usage = record.get("usage") or {}
        first = usage.get("first_turn") or {}
        cache = (
            "cold cache" if (first.get("cache_creation_input_tokens") or 0) > 0 else "warm cache"
        )
        out(
            f"  step {record['labels'].get('step')} ({record['action']}): {record['outcome']}, {cache}: FIRST-TURN CONTEXT "
            f"{usage.get('context_tokens_first_turn')} tokens (uncached {first.get('input_tokens')}, cache-created "
            f"{first.get('cache_creation_input_tokens')}, cache-read {first.get('cache_read_input_tokens')})"
        )
        out(
            f"      whole call: {usage.get('total_tokens')} tokens over {usage.get('turns')} turn(s), cost "
            f"{fmt(record.get('cost_usd'), '', 4)}, total {fmt(record['latency_s'].get('total'))}, first signal "
            f"{fmt(record['latency_s'].get('first_text_delta'))}, tool calls {len(record['tool_calls'])}, tools offered "
            f"{record['init'].get('tools')}, model {record['model']}, claude {record['init'].get('claude_code_version')}"
        )
    out("")
    out(f"MAIN STAGE (n={len(main)}; outcomes {analysis.outcomes(main)})")
    split = analysis.path_report(main)
    out(
        f"  paths {split['paths']}; {split['retried']} needed a retry turn, "
        f"{split['executor_refusals']} were refused by the executor at least once"
    )
    latency = analysis.latency_report(main)
    out(stats_line("full response (total)", latency["total"]))
    out(stats_line("first signal (first text delta)", latency["first_text_delta"]))
    out(stats_line("first event", latency["first_event"]))
    out(stats_line("first message_start", latency["first_message"]))
    out(stats_line("final answer, first delta", latency["final_answer_first_delta"]))
    out(stats_line("driver overhead before spawn", latency["launch_overhead"]))
    out(stats_line("  of which Python start-up", latency["python_startup"]))
    cost = analysis.cost_report(main)
    out(stats_line("cost per action", cost["cost_usd"], "", 4))
    out(stats_line("tokens per action (all turns)", cost["total_tokens"], "", 0))
    out(stats_line("context peak per action", cost["context_tokens_peak"], "", 0))
    out(stats_line("tool calls per action", cost["tool_calls"], "", 1))
    cache = analysis.cache_report(main)
    out(
        f"  prompt cache: read {cache['cache_read']}, created {cache['cache_creation']}, uncached {cache['uncached_input']} tokens "
        f"(read fraction {fmt(cache['read_fraction'], '', 2)})"
    )
    out("  by action:")
    for action, group in analysis.by_action(main).items():
        out(
            f"    {action:<14} n={group['n']:<2} total p50 {fmt(group['total'].get('p50'))} first-signal p50 "
            f"{fmt(group['first_text_delta'].get('p50'))} cost mean {fmt(group['cost_usd'].get('mean'), '', 4)} "
            f"tokens mean {fmt(group['total_tokens'].get('mean'), '', 0)} tools mean {fmt(group['tool_calls'].get('mean'), '', 1)}"
        )
    failed = [r for r in main if r.get("outcome") != "ok"]
    for record in failed:
        out(
            f"  NOT OK: step {record['labels'].get('step')} {record['action']} -> {record['outcome']}: {record['outcome_detail']}"
        )
    out("")
    out("COHERENCE (state real from day one: does the persisted state stay true?)")
    out(
        f"  invocations checked {coherence.invocations_checked} across sessions {coherence.sessions}; oracles: store invariants, a one-step"
    )
    out(
        "  rule replay per invocation, response against store, and a ledger replayed from the empty store compared at every session boundary"
    )
    for note in coherence.notes:
        out(f"  note: {note}")
    if coherence.contradictions:
        for contradiction in coherence.contradictions:
            out(f"  CONTRADICTION {contradiction.line()}")
    else:
        out("  no contradictions found")
    out(
        f"  gap notes: {coherence.gap_notes_found}/{coherence.gap_notes_expected} left where the node is silent; "
        f"{len(coherence.gap_notes_unexpected)} left where it is not"
    )
    for item in coherence.gap_notes_missing + coherence.gap_notes_unexpected:
        out(f"    {item.line()}")
    out(
        f"  contract: {len(coherence.contract_violations)} tool-call violations (the puntal must only run ./state)"
    )
    for item in coherence.contract_violations:
        out(f"    {item.line()}")
    extras = sorted({e for r in telemetry for e in r.get("scratch_extra_entries") or []})
    out(f"  files left in the run's scratch directory by any invocation: {extras or 'none'}")
    out(
        f"  permission denials reported by the CLI: {sum(r.get('permission_denials') or 0 for r in telemetry)}"
    )
    out("")
    out(
        "GO / NO-GO against the plan's starting points (adjustable; judged on the main stage, p95 for the latency criteria)"
    )
    out(
        verdict(
            latency["first_text_delta"].get("p95"),
            first_signal_max,
            label=f"first signal p95 < {first_signal_max:g}s",
        )
    )
    out(
        f"    (p50 {fmt(latency['first_text_delta'].get('p50'))}; {latency['first_text_delta'].get('n', 0)} of {len(main)} invocations produced a text delta)"
    )
    out(verdict(latency["total"].get("p95"), p95_max, label=f"full response p95 < {p95_max:g}s"))
    out(
        verdict(
            cost["cost_usd"].get("mean"),
            cost_mean_max,
            label=f"mean cost < ${cost_mean_max:g} per action",
        )
    )
    contradictions = len(coherence.contradictions)
    out(
        f"  zero contradictions over persisted state: {'PASS' if main and not contradictions else 'FAIL' if contradictions else 'NO DATA'}  ({contradictions} found)"
    )
    out(
        f"  (added) the puntal ran only ./state: {'PASS' if main and not coherence.contract_violations else 'FAIL' if coherence.contract_violations else 'NO DATA'}"
    )
    if reserve:
        out("")
        out(f"RESERVE PROBES (n={len(reserve)}; not part of the verdict above)")
        groups: dict[tuple, list[dict]] = {}
        for record in reserve:
            groups.setdefault((record["model"], record.get("effort")), []).append(record)
        for (model, effort), group in groups.items():
            out(f"  model {model} effort {effort or 'default'}: n={len(group)}")
            out(stats_line("  full response", analysis.latency_report(group)["total"]))
            out(stats_line("  first signal", analysis.latency_report(group)["first_text_delta"]))
            out(stats_line("  cost per action", analysis.cost_report(group)["cost_usd"], "", 4))
    machine = {
        "n": {"calibration": len(calibration), "main": len(main), "reserve": len(reserve)},
        "outcomes": analysis.outcomes(main),
        "paths": analysis.path_report(main),
        "latency": latency,
        "cost": cost,
        "cache": cache,
        "contradictions": [c.__dict__ for c in coherence.contradictions],
        "contract_violations": [c.__dict__ for c in coherence.contract_violations],
        "gap_notes": {"expected": coherence.gap_notes_expected, "found": coherence.gap_notes_found},
    }
    return "\n".join(lines) + "\n", machine


# ---------------------------------------------------------------------------------------------
# Entry point.
# ---------------------------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="measure.py", description=(__doc__ or "").split("\n\n")[0]
    )
    parser.add_argument("--workdir", default=str(REPO_ROOT / ".cache" / "puntal-bench"))
    commands = parser.add_subparsers(dest="command", required=True)

    def running(name: str, help_text: str) -> argparse.ArgumentParser:
        sub = commands.add_parser(name, help=help_text)
        sub.add_argument(
            "--dry-run", action="store_true", help="use the fake backend; spends nothing"
        )
        sub.add_argument(
            "--allow-real-calls",
            action="store_true",
            help="make REAL calls, counted against the cap",
        )
        sub.add_argument("--model", default=DEFAULT_MODEL)
        sub.add_argument(
            "--puntal-path",
            choices=["slow", "fast"],
            default="slow",
            help="the driver's path: `slow` (default) is the Phase 0 tool loop this bench was "
            "built to measure; `fast` plans in one turn and the bench's executor applies it",
        )
        sub.add_argument("--effort", default="")
        sub.add_argument(
            "--timeout",
            type=int,
            default=0,
            help="per-invocation safety timeout (default: the config's)",
        )
        sub.add_argument(
            "--counter-file", default="", help="where real calls are counted (default: per user)"
        )
        sub.add_argument(
            "--class-override",
            action="append",
            default=[],
            metavar="KEY=VALUE",
            help="a classes.puntal field",
        )
        sub.add_argument(
            "--puntal-override",
            action="append",
            default=[],
            metavar="KEY=VALUE",
            help="a puntal: field",
        )
        sub.add_argument(
            "--fake-fault",
            default="",
            help="dry run only: make the fake misbehave (see fake_claude.FAULTS)",
        )
        return sub

    running("calibrate", "2 calls with the smallest prompt: the context floor")
    main_stage = running("main", "3 sessions of 8 over one store")
    main_stage.add_argument("--session", choices=["1", "2", "3", "all"], required=True)
    main_stage.add_argument(
        "--pause-between-sessions",
        type=int,
        default=0,
        help="seconds (>300 lets the prompt cache expire)",
    )
    reserve = running("reserve", "up to 4 adaptive probes on the store the main stage built")
    reserve.add_argument(
        "--count", type=int, choices=range(1, RESERVE_MAX_PER_RUN + 1), required=True
    )
    summary = commands.add_parser("summarize", help="numbers and coherence from the raw files")
    summary.add_argument("--json", action="store_true")
    summary.add_argument("--first-signal-max", type=float, default=5.0)
    summary.add_argument("--p95-max", type=float, default=30.0)
    summary.add_argument("--cost-mean-max", type=float, default=0.10)
    status = commands.add_parser(
        "status", help="how much of the cap is spent, and how far the stages got"
    )
    status.add_argument("--counter-file", default="")
    commands.add_parser("check-store", help="the invariants over the store as it is now")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    workdir = pathlib.Path(args.workdir).resolve()
    if args.command == "summarize":
        if not (workdir / "telemetry.jsonl").is_file():
            raise Refusal(
                f"{workdir / 'telemetry.jsonl'} does not exist: nothing has been measured there"
            )
        text, machine = summarize(
            workdir,
            first_signal_max=args.first_signal_max,
            p95_max=args.p95_max,
            cost_mean_max=args.cost_mean_max,
        )
        print(
            json.dumps(machine, indent=1) if args.json else text, end="" if not args.json else "\n"
        )
        return 0
    if args.command == "status":
        counter = pathlib.Path(args.counter_file) if args.counter_file else default_counter_file()
        trace = read_json_lines(workdir / "trace.jsonl")
        print(f"real calls counted: {real_calls_used(counter)} of {REAL_CALL_CAP} ({counter})")
        for stage in ("calibration", "main", "reserve"):
            print(
                f"{stage}: {sum(1 for r in trace if r['stage'] == stage)} invocations in {workdir / 'trace.jsonl'}"
            )
        return 0
    if args.command == "check-store":
        violations = domain.check_invariants(Store(workdir / "store").dump())
        for violation in violations:
            print(f"[{violation.code}] {violation.message}")
        print("store invariants hold" if not violations else f"{len(violations)} violation(s)")
        return 1 if violations else 0

    mode = resolve_mode(args)
    if args.fake_fault and mode != "dry":
        raise Refusal("--fake-fault only makes sense with --dry-run")
    if mode == "real":
        removed = scrub_backend_overrides()
        if removed:
            print(f"real mode: ignoring {removed} from the environment", flush=True)
    context = Context(args, mode=mode)
    context.prepare()
    print(
        f"mode: {mode}{' (fake backend, nothing is spent)' if mode == 'dry' else ' -- REAL calls'}; workdir {context.workdir}",
        flush=True,
    )
    if args.command == "calibrate":
        stage_calibrate(context)
    elif args.command == "main":
        stage_main(context, args.session)
    else:
        stage_reserve(context, args.count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
