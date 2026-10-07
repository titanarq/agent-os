"""The owner's order of the backlog, read back from the Project.

The owner orders the branches by writing a number in the Project's order field (lower first).
This module only EXPOSES that order; what dispatch does with it is the planner's concern (#117).
A requirement without a number follows the numbered ones, in tree (id) order.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from agent_os.product.board.branches import build_branches, requirement_id_in
from agent_os.product.board.project import BoardError, GhProjectClient
from agent_os.product.board.sync import find_project, item_body, item_field_value
from agent_os.product.config import BoardConfig
from agent_os.product.tree.loader import Tree


@dataclass(frozen=True)
class OwnerOrder:
    ordered: list[str]
    unordered: list[str]

    @property
    def requirement_ids(self) -> list[str]:
        return [*self.ordered, *self.unordered]

    def to_json(self) -> str:
        return json.dumps(
            {
                "ordered": self.ordered,
                "unordered": self.unordered,
                "requirements": self.requirement_ids,
            },
            indent=2,
        )


def read_owner_order(tree: Tree, client: GhProjectClient, config: BoardConfig) -> OwnerOrder:
    project = find_project(client, config)
    if project is None:
        raise BoardError(
            f"no Project titled {config.title!r}: run `agent-os-tree board sync` first"
        )
    numbers: dict[str, float] = {}
    for item in client.list_items(project["number"]):
        requirement_id = requirement_id_in(item_body(item))
        value = item_field_value(item, config.order_field)
        if requirement_id is not None and isinstance(value, int | float):
            numbers[requirement_id] = float(value)
    in_tree = [branch.requirement_id for branch in build_branches(tree)]
    ordered = sorted(
        (rid for rid in in_tree if rid in numbers), key=lambda rid: (numbers[rid], rid)
    )
    return OwnerOrder(ordered, [rid for rid in in_tree if rid not in numbers])
