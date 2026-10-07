"""`agent-os-tree`: the doctor, the slice and the ticket renderer of the product tree.

    agent-os-tree validate [--root DIR] [--json]       # alias: doctor
        # one line per defect, `<file>: <code>: <what is wrong>`, exit 1 if there is any. The
        # tree must not ship red, the way no host literal may ship in `agent_os/`.
    agent-os-tree context NODE [--root DIR] [--json]
        # the slice of one node: the node, its ancestors with the acceptance each one carries (what
        # the node's work serves and must not break), the decisions in force on that chain (an
        # `under-review` one labelled as still obeyed), their sources. Nothing else.
    agent-os-tree compile [--root DIR] [--json] [--out-dir DIR] [--budget-class C] [--label L ...]
        # the dispatch tickets of every dispatchable node, and an escalation for each node that
        # lacks a verification. Renders only: no issue is created and no network is touched.
    agent-os-tree trailers --base REF [--head REF] [--root DIR] [--json]
        # every commit of REF..HEAD that touches the tree must carry one `Node-Change: usage|rework|owner`
        # trailer; one line per commit that does not, exit 1. Reads git only.

Exit status: 0 on success, 1 on a red tree or a refusal (one line on stderr saying why), 2 on a
usage error. The root is `--root`, else `tree.root` of `config/agents.yaml` under the host's root;
a root that is not a directory is an error, never a guess.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections.abc import Sequence

from agent_os import lib
from agent_os.cli import host_root
from agent_os.product.tree.checks import check_tree
from agent_os.product.tree.compile import (
    CompileError,
    compile_tree,
    render_compile_json,
    render_compile_text,
    write_compile_files,
)
from agent_os.product.tree.loader import Defect, TreeRootError, load_tree, require_tree_root
from agent_os.product.tree.slicing import (
    SliceError,
    build_slice,
    render_slice_json,
    render_slice_markdown,
)
from agent_os.product.tree.trailers import TrailerError, check_node_change_trailers

PROGRAM = "agent-os-tree"


def display_path(path: pathlib.Path) -> str:
    """`path` as a person would type it: relative to the working directory when it lies under it,
    absolute otherwise -- so a defect line is a path an editor can open."""
    try:
        return str(path.relative_to(pathlib.Path.cwd()))
    except ValueError:
        return str(path)


def format_defect(defect: Defect) -> str:
    return f"{display_path(defect.path)}: {defect.code}: {defect.message}"


def _tree_root_label(root: pathlib.Path) -> str:
    """How a ticket names the tree root: relative to the host's root when it lies under it."""
    try:
        return root.relative_to(host_root()).as_posix()
    except ValueError:
        return str(root)


def _load_config(config_path: pathlib.Path | str | None) -> lib.AgentsConfig:
    return lib.load_agents_config(config_path or lib.DEFAULT_AGENTS_CONFIG)


def _resolve_root(root_option: str | None, config_path: pathlib.Path | str | None) -> pathlib.Path:
    if root_option:
        return require_tree_root(root_option)
    try:
        configured = _load_config(config_path).tree.root
    except lib.CONFIG_LOAD_ERRORS as error:
        raise TreeRootError(
            "no --root given and the tree root cannot be read from the config: "
            + lib.config_load_failure(error, config_path or lib.DEFAULT_AGENTS_CONFIG)
        ) from error
    return require_tree_root(host_root() / configured)


def _validate(args: argparse.Namespace, config_path) -> int:
    root = _resolve_root(args.root, config_path)
    tree = load_tree(root)
    defects = check_tree(tree)
    if args.json:
        print(
            json.dumps(
                {
                    "ok": not defects,
                    "root": str(root),
                    "nodes": len(tree.nodes),
                    "decisions": len(tree.decisions),
                    "defects": [
                        {
                            "path": display_path(defect.path),
                            "check": defect.code,
                            "message": defect.message,
                        }
                        for defect in defects
                    ],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    elif defects:
        for defect in defects:
            print(format_defect(defect))
        files = len({defect.path for defect in defects})
        print(f"FAIL: {len(defects)} defect(s) in {files} file(s) under {display_path(root)}")
    else:
        print(
            f"ok: {len(tree.nodes)} node(s), {len(tree.decisions)} decision(s) "
            f"under {display_path(root)}"
        )
    return 1 if defects else 0


def _context(args: argparse.Namespace, config_path) -> int:
    tree = load_tree(_resolve_root(args.root, config_path))
    try:
        cut = build_slice(tree, args.node)
    except SliceError as error:
        print(f"{PROGRAM}: {error}", file=sys.stderr)
        for defect in error.defects:
            print(f"  {format_defect(defect)}", file=sys.stderr)
        return 1
    print(render_slice_json(cut) if args.json else render_slice_markdown(cut), end="")
    return 0


def _compile(args: argparse.Namespace, config_path) -> int:
    root = _resolve_root(args.root, config_path)
    try:
        config = _load_config(config_path)
    except lib.CONFIG_LOAD_ERRORS as error:
        print(
            f"{PROGRAM}: compile needs the config for the budget classes and labels: "
            + lib.config_load_failure(error, config_path or lib.DEFAULT_AGENTS_CONFIG),
            file=sys.stderr,
        )
        return 1
    try:
        result = compile_tree(
            load_tree(root),
            config,
            budget_class=args.budget_class or config.tree.ticket_budget_class,
            tree_root=_tree_root_label(root),
            extra_labels=args.label or [],
        )
    except CompileError as error:
        print(f"{PROGRAM}: {error}", file=sys.stderr)
        for defect in error.defects:
            print(f"  {format_defect(defect)}", file=sys.stderr)
        return 1
    print(render_compile_json(result) if args.json else render_compile_text(result), end="")
    if args.out_dir:
        for path in write_compile_files(result, pathlib.Path(args.out_dir)):
            print(f"wrote {display_path(path.resolve())}", file=sys.stderr)
    return 0


def _trailers(args: argparse.Namespace, config_path) -> int:
    root = _resolve_root(args.root, config_path)
    try:
        defects = check_node_change_trailers(root, args.base, args.head)
    except TrailerError as error:
        print(f"{PROGRAM}: {error}", file=sys.stderr)
        return 1
    if args.json:
        listed = [vars(defect) for defect in defects]
        print(json.dumps({"ok": not defects, "defects": listed}, indent=2, ensure_ascii=False))
        return 1 if defects else 0
    for defect in defects:
        print(f"{defect.commit[:10]} {defect.subject}: {defect.code}: {defect.message}")
    return 1 if defects else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROGRAM, description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--root", help="the tree directory (default: `tree.root` of config/agents.yaml)"
    )
    common.add_argument("--json", action="store_true", help="machine-readable output")
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("validate", "doctor"):
        p = sub.add_parser(name, parents=[common], help="the tree doctor: exit 1 on any defect")
        p.set_defaults(handler=_validate)

    p = sub.add_parser("context", parents=[common], help="the slice of one node")
    p.add_argument("node", help="the node's id")
    p.set_defaults(handler=_context)

    p = sub.add_parser(
        "compile", parents=[common], help="render dispatch tickets from dispatchable nodes"
    )
    p.add_argument("--out-dir", help="also write <node id>.md per ticket and compile.json here")
    p.add_argument(
        "--budget-class",
        help="the worker class the tickets name (default: tree.ticket_budget_class)",
    )
    p.add_argument("--label", action="append", help="one more label on every ticket (repeatable)")
    p.set_defaults(handler=_compile)

    p = sub.add_parser(
        "trailers", parents=[common], help="every commit touching the tree carries Node-Change"
    )
    p.add_argument("--base", required=True, help="the range starts after this ref")
    p.add_argument("--head", default="HEAD", help="the range ends at this ref (default: HEAD)")
    p.set_defaults(handler=_trailers)
    return parser


def main(
    argv: Sequence[str] | None = None, *, config_path: pathlib.Path | str | None = None
) -> int:
    """Runs one command and returns its exit status; `config_path` replaces the default
    `config/agents.yaml` for a caller (a test) that has a config of its own."""
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args, config_path)
    except TreeRootError as error:
        print(f"{PROGRAM}: {error}", file=sys.stderr)
        return 1
