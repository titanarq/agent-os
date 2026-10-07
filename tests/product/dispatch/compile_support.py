"""What the compile tests share: the example config, and a tree under `tmp_path` compiled with it.

Imported by name (`from compile_support import compiled`); `pyproject.toml` puts this directory on
the test `sys.path`. Nothing here reads the network, a backend or a real host tree.
"""

from __future__ import annotations

import pathlib

import yaml
from conftest import EXAMPLE_CONFIG

from agent_os.lib import load_agents_config
from agent_os.product.dispatch.markers import render_marker_lines
from agent_os.product.dispatch.results import CompileResult, Ticket
from agent_os.product.tree.compile import compile_tree
from agent_os.product.tree.loader import load_tree

CONFIG = load_agents_config(EXAMPLE_CONFIG)
BUDGET_CLASS = "mechanical-qwen"


def compiled(root: pathlib.Path, **overrides) -> CompileResult:
    options = {"budget_class": BUDGET_CLASS, "tree_root": "product", **overrides}
    return compile_tree(load_tree(root), CONFIG, **options)


def one_ticket(root: pathlib.Path, node_id: str) -> Ticket:
    (ticket,) = [t for t in compiled(root).tickets if t.node_id == node_id]
    return ticket


def write_v2_config(path: pathlib.Path, *, dispatch_by_node: bool = True) -> pathlib.Path:
    """The example config with `tree.dispatch_by_node` set, written where a test points the
    mechanism's `DEFAULT_AGENTS_CONFIG`."""
    data = yaml.safe_load(EXAMPLE_CONFIG.read_text())
    data["tree"]["dispatch_by_node"] = dispatch_by_node
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def ticket_row(number: int, body: str) -> dict:
    return {"number": number, "body": body}


def body(node_id: str, *, depends_on=(), touches=()) -> str:
    """A ticket body reduced to what dispatch reads: the marker lines."""
    lines = render_marker_lines(node_id, depends_on, touches)
    return "Objective\n\n" + "\n".join(lines) + "\n"
