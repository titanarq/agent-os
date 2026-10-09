"""`python -m agent_os.product.dispatch start-gate ISSUE [RUNNING ...]`: the driver's last question.

`worker_task.sh start` asks it with the issue it is about to start and the issues the other workers
are running. Silent and exit 0 in a host that is not v2; in a v2 host, exit 1 with one line per
reason when a rule of `agent_os.product.dispatch.rules` refuses the issue.

`python -m agent_os.product.dispatch headroom [--json]` is the planner's and the control's question:
can more work run at once right now (`agent_os.product.dispatch.headroom`). Read-only, exit 0.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from agent_os import issues, lib
from agent_os.product.dispatch.headroom.command import headroom
from agent_os.product.dispatch.rules import is_v2_host, tree_dispatch_refusals

OPEN_ISSUES_LIMIT = "500"


def _open_rows() -> list[dict]:
    return issues.gh_json(
        "issue", "list", "--state", "open", "--json", "number,body", "--limit", OPEN_ISSUES_LIMIT
    )


def start_gate(issue_number: int, running_numbers: Sequence[int]) -> int:
    if not is_v2_host(lib.load_agents_config(lib.DEFAULT_AGENTS_CONFIG)):
        return 0
    open_rows = _open_rows()
    by_number = {int(row["number"]): row for row in open_rows}
    if issue_number not in by_number:
        print(f"refusing to dispatch: issue #{issue_number} is not an open issue", file=sys.stderr)
        return 1
    running = [by_number[number] for number in running_numbers if number in by_number]
    refusals = tree_dispatch_refusals(by_number[issue_number], open_rows, running)
    for refusal in refusals:
        print(f"refusing to dispatch: issue #{issue_number}: {refusal}", file=sys.stderr)
    return 1 if refusals else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent_os.product.dispatch")
    sub = parser.add_subparsers(dest="command", required=True)
    gate = sub.add_parser("start-gate", help="may this issue start, given what is running")
    gate.add_argument("issue", type=int)
    gate.add_argument("running", type=int, nargs="*")
    headroom_parser = sub.add_parser(
        "headroom", help="can more work run at once right now, and what holds each ready issue back"
    )
    headroom_parser.add_argument("--json", action="store_true", help="the same answer as JSON")
    args = parser.parse_args(argv)
    if args.command == "headroom":
        return headroom(as_json=args.json)
    return start_gate(args.issue, args.running)
