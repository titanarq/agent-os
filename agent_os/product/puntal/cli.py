"""The command line: `puntal_task.sh` and the module that `python -m agent_os.product.puntal` runs."""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import json
import os
import pathlib
import shlex
import sys

from agent_os.lib import HOST_ROOT
from agent_os.product.puntal.constants import (
    EXIT_ANSWERED,
    EXIT_NOT_RUN,
    PATH_FAST,
    PATH_SLOW,
    PuntalRefused,
)
from agent_os.product.puntal.fast.brief import build_brief
from agent_os.product.puntal.fast.pre_helper import load_declared_state
from agent_os.product.puntal.invocation import invoke
from agent_os.product.puntal.json_api import envelope, refusal_envelope, request_from_json
from agent_os.product.puntal.options import (
    Options,
    Request,
    build_request,
    resolve_options,
    run_dir_for,
)
from agent_os.product.puntal.stream.launch import Clock
from agent_os.product.puntal.telemetry.feedback import VERDICTS, record_feedback
from agent_os.product.puntal.telemetry.post_helpers import record_invocation
from agent_os.product.puntal.turn import flags_for


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="puntal_task.sh",
        description="Answers ONE live UI action with one headless agent process "
        "(`puntal_task.sh feedback ...` records the owner's verdict on an answer).",
    )
    parser.add_argument("--action", help="the UI action that was triggered")
    parser.add_argument(
        "--node-file", help="the node slice (use case + ancestor goals); `-` is stdin"
    )
    parser.add_argument("--node-id", help="the node's id (default: the node file's stem)")
    parser.add_argument("--payload", help="the action's payload, as text")
    parser.add_argument("--payload-file", help="the action's payload from a file; `-` is stdin")
    parser.add_argument("--state-file", help="the relevant persisted state the app already holds")
    parser.add_argument(
        "--read",
        action="append",
        default=[],
        metavar="COMMAND",
        help="a read the pre-helper loads, besides the node's own `reads:` "
        "(e.g. 'get tickets {payload.id}'); repeatable",
    )
    parser.add_argument("--session-id", help="the app's own session id, recorded in the telemetry")
    parser.add_argument("--invocation-id", help="an id for this invocation (default: a UUID)")
    parser.add_argument("--label", action="append", default=[], metavar="KEY=VALUE")
    parser.add_argument("--model", help="override the puntal class's model")
    parser.add_argument("--effort", default=None, help="override puntal.effort (`claude --effort`)")
    parser.add_argument("--timeout", type=int, default=0, help="override puntal.timeout_seconds")
    parser.add_argument(
        "--path",
        choices=(PATH_FAST, PATH_SLOW),
        default=None,
        help="`fast` (default): plan in one turn, code executes; `slow`: the tool loop, forced",
    )
    parser.add_argument(
        "--persistence-command", default="", help="override the persistence command"
    )
    parser.add_argument("--executor-command", default="", help="override the executor command")
    parser.add_argument(
        "--json",
        action="store_true",
        help="the shell API: one JSON request on stdin, one JSON envelope on stdout",
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="with --json: do not apply the operations, hand them back for the app to apply",
    )
    parser.add_argument("--telemetry-file", help="append the record here, not to the run dir's")
    parser.add_argument("--dry-run", action="store_true", help="print the launch; spend nothing")
    return parser


def build_feedback_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="puntal_task.sh feedback",
        description="Record the owner's verdict on one invocation, in `feedback.jsonl`.",
    )
    parser.add_argument("--invocation-id", required=True)
    parser.add_argument("--verdict", required=True, choices=VERDICTS)
    parser.add_argument("--note", default="", help="why, in the owner's words")
    parser.add_argument("--retried-as", help="with `retry`: the invocation id of the new attempt")
    parser.add_argument("--telemetry-file", help="where the invocation's record is")
    parser.add_argument("--feedback-file", help="default: feedback.jsonl beside the telemetry")
    return parser


def describe_launch(request: Request, options: Options, brief: str) -> str:
    on_slow_path = options.path == PATH_SLOW
    flags = flags_for(options, with_state_tool=on_slow_path)
    contract = options.slow_contract if on_slow_path else options.fast_contract
    return "\n".join(
        [
            f"class:       {options.class_name}",
            f"backend:     {options.backend} ({options.executable})",
            f"model:       {options.model}",
            f"effort:      {options.effort or '(CLI default)'}",
            f"path:        {options.path}",
            f"action:      {request.action}",
            f"node:        {request.node_id}",
            f"reads:       {request.declared_reads or '(none declared)'}",
            f"persistence: {options.persistence_command}",
            f"executor:    {options.executor_command or '(none)'}",
            f"ceilings:    {dataclasses.asdict(options.ceilings)}",
            f"telemetry:   {options.telemetry_file}",
            f"flags:       {shlex.join(flags)}",
            "--- contract (system prompt) ---",
            contract.rstrip("\n"),
            "--- brief (first message) ---",
            brief.rstrip("\n"),
        ]
    )


def dry_run_brief(request: Request, options: Options) -> str:
    """The brief a real run would send, with the node's reads really loaded: they only read."""
    loaded = None
    if request.declared_reads:
        loaded = load_declared_state(
            request.declared_reads,
            payload_text=request.payload,
            persistence_command=shlex.split(options.persistence_command),
            allowed_subcommands=options.read_subcommands,
            host_root=options.host_root,
            timeout_seconds=options.ceilings.timeout_seconds,
        ).text
    elif options.path == PATH_FAST:
        loaded = ""
    return build_brief(
        node_slice=request.node_slice,
        action=request.action,
        payload=request.payload,
        relevant_state=request.relevant_state,
        loaded_state=loaded,
    )


def release_stdout() -> None:
    """Hands the caller its answer NOW: flushes and closes stdout, so a reader waiting for end of
    file stops waiting while the post-helpers still run. Only the process's own stdout is closed."""
    with contextlib.suppress(OSError, ValueError):
        sys.stdout.flush()
        if sys.stdout is sys.__stdout__:
            sys.stdout.close()


def feedback_main(argv: list[str]) -> int:
    args = build_feedback_parser().parse_args(argv)
    run_dir = run_dir_for(HOST_ROOT)
    telemetry_file = run_dir / "telemetry.jsonl"
    if args.telemetry_file:
        telemetry_file = pathlib.Path(args.telemetry_file)
    feedback_file = (
        pathlib.Path(args.feedback_file)
        if args.feedback_file
        else telemetry_file.parent / "feedback.jsonl"
    )
    try:
        record = record_feedback(
            invocation_id=args.invocation_id,
            verdict=args.verdict,
            note=args.note,
            retried_as=args.retried_as,
            telemetry_file=telemetry_file,
            feedback_file=feedback_file,
        )
    except PuntalRefused as refusal:
        print(f"puntal feedback not recorded: {refusal}", file=sys.stderr)
        return EXIT_NOT_RUN
    print(json.dumps(record, ensure_ascii=False))
    return EXIT_ANSWERED


def answer_main(argv: list[str], clock: Clock) -> int:
    args = build_parser().parse_args(argv)
    request = None
    try:
        if args.json:
            if args.action or args.node_file:
                raise PuntalRefused("--json takes the whole request on stdin, not flags")
            request = request_from_json(sys.stdin.read())
        else:
            if args.plan_only:
                raise PuntalRefused("--plan-only needs --json: the plan has to come back somewhere")
            if args.action is None or args.node_file is None:
                raise PuntalRefused("--action and --node-file are required (`-` reads stdin)")
            request = build_request(args)
        options = resolve_options(args=args, host_root=HOST_ROOT)
        if args.dry_run:
            print(describe_launch(request, options, dry_run_brief(request, options)))
            return EXIT_ANSWERED
    except PuntalRefused as refusal:
        print(f"puntal not run: {refusal}", file=sys.stderr)
        if args.json:
            print(json.dumps(refusal_envelope(refusal, request.invocation_id if request else None)))
        return EXIT_NOT_RUN
    result = invoke(request, options, clock)
    trace = result.trace
    if result.status != EXIT_ANSWERED:
        print(f"puntal {trace.outcome}: {trace.outcome_detail}", file=sys.stderr)
    if args.json:
        print(
            json.dumps(envelope(request, result, plan_only=options.plan_only), ensure_ascii=False)
        )
    elif result.status == EXIT_ANSWERED:
        # A run that did not finish has no response worth handing the app: what it said before it
        # was cut is in the telemetry and the log, and the exit status says it failed.
        print(result.answer)
    release_stdout()
    if trace.gap_note:
        print(f"puntal gap note: {trace.gap_note}", file=sys.stderr)
    try:
        record_invocation(request, options, clock, result)
    except OSError as error:
        # The click was answered; a telemetry line that could not be written is reported, not turned
        # into a failed click.
        print(f"puntal telemetry not written: {error}", file=sys.stderr)
    return result.status


def main(argv: list[str] | None = None) -> int:
    clock = Clock(
        float(os.environ["PUNTAL_LAUNCH_EPOCH"]) if os.environ.get("PUNTAL_LAUNCH_EPOCH") else None
    )
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "feedback":
        return feedback_main(arguments[1:])
    return answer_main(arguments, clock)
