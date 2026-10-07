"""`agent-os-tree board sync|order`: the progress board from the tree, and the owner's order back.

    agent-os-tree board sync [--dry-run] [--json]    # tree -> GitHub Project, idempotent
    agent-os-tree board order [--out FILE]           # the owner's order of the backlog, as JSON

The tree and config are resolved by `agent_os.product.tree.cli`, which registers this and passes
them in, so the board never re-implements how a tree root is found.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from agent_os.product.board.order import read_owner_order
from agent_os.product.board.project import BoardError, GhProjectClient
from agent_os.product.board.sync import sync_board
from agent_os.product.config import BoardConfig
from agent_os.product.tree.loader import Tree


def add_board_parser(subparsers, common: argparse.ArgumentParser, handler) -> None:
    board = subparsers.add_parser("board", help="the progress board: tree -> GitHub Project")
    actions = board.add_subparsers(dest="board_action", required=True)
    sync = actions.add_parser("sync", parents=[common], help="generate the Project from the tree")
    sync.add_argument("--dry-run", action="store_true", help="print the plan, change nothing")
    order = actions.add_parser("order", parents=[common], help="read the owner's order back")
    order.add_argument("--out", help="also write the order as JSON to this file")
    board.set_defaults(handler=handler)


def run_board(args: argparse.Namespace, tree: Tree, config: BoardConfig, program: str) -> int:
    client = GhProjectClient(config.owner)
    try:
        if args.board_action == "sync":
            plan = sync_board(tree, client, config, dry_run=args.dry_run)
            if args.json:
                print(json.dumps({"dry_run": args.dry_run, "changes": plan.describe()}, indent=2))
            else:
                prefix = "dry-run: " if args.dry_run else ""
                print("\n".join(prefix + line for line in plan.describe()))
            return 0
        owner_order = read_owner_order(tree, client, config)
    except BoardError as error:
        print(f"{program}: {error}", file=sys.stderr)
        return 1
    print(owner_order.to_json())
    if args.out:
        pathlib.Path(args.out).write_text(owner_order.to_json() + "\n", encoding="utf-8")
    return 0
