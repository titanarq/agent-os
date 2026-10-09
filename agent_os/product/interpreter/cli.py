"""The command line: `python -m agent_os.product.interpreter interpret` (`bin/interpreter_task.sh`).

    interpret [--request FILE|-] [--tree-root DIR] [--model M] [--timeout SECONDS]
              [--telemetry-file F] [--dry-run]

STDIN (or FILE) is the request, STDOUT is ONE JSON envelope whatever happened, STDERR the diagnostics.
The exit status is the envelope's `exit_status`: 0 interpreted, 1 the backend failed, 2 not run,
3 the run broke the contract, 4 a ceiling cut it, 5 the answer was not a valid interpretation after
its retry, 124 the safety timeout killed it. The contract is `docs/FEEDBACK_INTERPRETER.md`.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from agent_os.lib import HOST_ROOT
from agent_os.product.interpreter.brief import build_brief
from agent_os.product.interpreter.constants import OUTCOME_EXIT_STATUS, InterpreterRefused
from agent_os.product.interpreter.envelope import refusal_envelope, success_envelope
from agent_os.product.interpreter.options import resolve_options
from agent_os.product.interpreter.request import Request, parse_request
from agent_os.product.interpreter.run import interpret, telemetry_request
from agent_os.product.puntal.cli import release_stdout
from agent_os.product.puntal.stream.launch import Clock
from agent_os.product.puntal.telemetry.post_helpers import record_invocation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="interpreter_task.sh")
    commands = parser.add_subparsers(dest="command", required=True)
    interpret_parser = commands.add_parser(
        "interpret", help="interpret the owner's latest chat message in a test session"
    )
    interpret_parser.add_argument("--request", default="-", help="the request JSON; `-` is stdin")
    interpret_parser.add_argument("--tree-root", help="the product tree (default: `tree.root`)")
    interpret_parser.add_argument("--model", help="override the interpreter class's model")
    interpret_parser.add_argument("--timeout", type=int, default=0)
    interpret_parser.add_argument("--telemetry-file")
    interpret_parser.add_argument("--dry-run", action="store_true", help="print the launch only")
    return parser


def _read_request_text(source: str) -> str:
    if source == "-":
        return sys.stdin.read()
    path = pathlib.Path(source)
    if not path.is_file():
        raise InterpreterRefused(f"the request {source!r} is not a file")
    return path.read_text()


def _refuse(detail: str, request: Request | None = None) -> int:
    print(f"interpreter not run: {detail}", file=sys.stderr)
    print(json.dumps(refusal_envelope(detail, request), ensure_ascii=False))
    return OUTCOME_EXIT_STATUS["not_run"]


def main(argv: list[str] | None = None) -> int:
    clock = Clock(None)
    args = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    request = None
    try:
        options, settings, default_tree_root = resolve_options(
            host_root=HOST_ROOT,
            model=args.model,
            timeout_seconds=args.timeout,
            telemetry_file=args.telemetry_file,
        )
        tree_root = pathlib.Path(args.tree_root) if args.tree_root else default_tree_root
        request = parse_request(_read_request_text(args.request), tree_root=tree_root)
    except InterpreterRefused as refusal:
        return _refuse(str(refusal), request)
    if args.dry_run:
        print(f"model:    {options.model} ({options.executable})")
        print(f"ceilings: {options.ceilings}")
        print("--- contract (system prompt) ---")
        print(options.fast_contract.rstrip("\n"))
        print("--- brief (first message) ---")
        print(
            build_brief(request, max_thread_messages=settings.max_thread_messages, rejection=None)
        )
        return 0
    outcome = interpret(request, options, settings, clock)
    if outcome.exit_status:
        print(f"interpreter {outcome.outcome}: {outcome.detail}", file=sys.stderr)
    print(json.dumps(success_envelope(request, outcome), ensure_ascii=False))
    release_stdout()
    try:
        record_invocation(telemetry_request(request), options, clock, outcome.result)
    except OSError as error:
        print(f"interpreter telemetry not written: {error}", file=sys.stderr)
    return outcome.exit_status


if __name__ == "__main__":
    sys.exit(main())
