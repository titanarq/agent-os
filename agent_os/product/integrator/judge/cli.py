"""The command line: `python -m agent_os.product.integrator.judge judge` (`bin/integrator_task.sh`).

    judge [--request FILE|-] [--model M] [--dry-run]

STDIN (or FILE) is the group's index (`index.parse_index`), STDOUT is ONE JSON object whatever
happened: the final groups, every pull request alone when the judgment could not be had. The exit
status is the outcome's: 0 judged, 1 the backend failed, 2 not run, 3 contract violation, 4 a
ceiling cut it, 5 an answer that does not partition the input, 124 the safety timeout.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from agent_os.lib import HOST_ROOT
from agent_os.product.integrator.judge.index import (
    GroupIndex,
    GroupIndexError,
    build_brief,
    parse_index,
)
from agent_os.product.integrator.judge.options import JudgeRefused, resolve_options
from agent_os.product.integrator.judge.run import judge_group, not_judged
from agent_os.product.puntal.stream.launch import Clock


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="integrator_task.sh")
    commands = parser.add_subparsers(dest="command", required=True)
    judge = commands.add_parser("judge", help="judge whether the proposed group is independent")
    judge.add_argument("--request", default="-", help="the index JSON; `-` is stdin")
    judge.add_argument("--model", help="override the integrator class's model")
    judge.add_argument("--dry-run", action="store_true", help="print the prompt and the brief only")
    return parser


def _read_request_text(source: str) -> str:
    if source == "-":
        return sys.stdin.read()
    path = pathlib.Path(source)
    if not path.is_file():
        raise GroupIndexError(f"the request {source!r} is not a file")
    return path.read_text()


def main(argv: list[str] | None = None) -> int:
    clock = Clock(None)
    arguments = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    index: GroupIndex | None = None
    try:
        index = parse_index(_read_request_text(arguments.request))
        options = resolve_options(host_root=HOST_ROOT, model=arguments.model)
    except (GroupIndexError, JudgeRefused) as refusal:
        print(f"integrator judge not run: {refusal}", file=sys.stderr)
        if index is None:
            print(
                json.dumps(
                    {"outcome": "not_run", "exit_status": 2, "detail": str(refusal), "groups": []}
                )
            )
        else:
            print(json.dumps(not_judged(index, "not_run", str(refusal)).as_json()))
        return 2
    if arguments.dry_run:
        print(f"model:    {options.model} ({options.executable})")
        print(f"ceilings: {options.ceilings}")
        print("--- contract (system prompt) ---")
        print(options.fast_contract.rstrip("\n"))
        print("--- brief (first message) ---")
        print(build_brief(index))
        return 0
    judgment = judge_group(index, options, clock)
    if judgment.exit_status:
        print(f"integrator judge {judgment.outcome}: {judgment.detail}", file=sys.stderr)
    print(json.dumps(judgment.as_json(), ensure_ascii=False))
    return judgment.exit_status


if __name__ == "__main__":
    sys.exit(main())
