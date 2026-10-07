"""The idempotent sync from the tree to the Project: a plan of changes, then its application.

The plan is computed from what the Project holds now, so running it twice makes the second plan
empty. A card whose requirement left the tree is reported as an orphan and kept: deleting it would
drop the owner's order on it, and the files, not the Project, are the record.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from agent_os.product.board.branches import (
    Branch,
    branch_progress_summary,
    branch_title,
    build_branches,
    render_branch_body,
    requirement_id_in,
)
from agent_os.product.board.project import GhProjectClient
from agent_os.product.config import BoardConfig
from agent_os.product.tree.loader import Tree

FIELD_TYPES = ("progress_field", "TEXT"), ("order_field", "NUMBER")


def item_body(item: dict) -> str:
    return (item.get("content") or {}).get("body") or item.get("body") or ""


def item_field_value(item: dict, field_name: str):
    """A field's value on an `item-list` entry, which `gh` flattens under the lower-cased name."""
    wanted = field_name.lower()
    for key, value in item.items():
        if key.lower() == wanted:
            return value
    return None


def find_project(client: GhProjectClient, config: BoardConfig) -> dict | None:
    if config.number:
        return client.view_project(config.number)
    matching = [project for project in client.list_projects() if project["title"] == config.title]
    return matching[0] if matching else None


@dataclass
class BoardPlan:
    project_to_create: str | None = None
    fields_to_create: list[str] = field(default_factory=list)
    items_to_create: list[Branch] = field(default_factory=list)
    items_to_update: list[tuple[dict, Branch]] = field(default_factory=list)
    orphans: list[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (
            self.project_to_create
            or self.fields_to_create
            or self.items_to_create
            or self.items_to_update
        )

    def describe(self) -> list[str]:
        lines = []
        if self.project_to_create:
            lines.append(f"create project {self.project_to_create!r}")
        lines += [f"create field {name}" for name in self.fields_to_create]
        lines += [f"create item {branch.requirement_id}" for branch in self.items_to_create]
        lines += [f"update item {branch.requirement_id}" for _, branch in self.items_to_update]
        lines += [
            f"orphan item {requirement_id} (requirement no longer in the tree; kept)"
            for requirement_id in self.orphans
        ]
        return lines or ["board is up to date"]


def _is_stale(item: dict, branch: Branch, config: BoardConfig) -> bool:
    return (
        item_body(item) != render_branch_body(branch)
        or item.get("title") != branch_title(branch)
        or item_field_value(item, config.progress_field) != branch_progress_summary(branch)
    )


def plan_board(
    tree: Tree, project: dict | None, fields: list[dict], items: list[dict], config: BoardConfig
) -> BoardPlan:
    plan = BoardPlan()
    if project is None:
        plan.project_to_create = config.title
    existing_field_names = {candidate["name"] for candidate in fields}
    plan.fields_to_create = [
        getattr(config, key)
        for key, _ in FIELD_TYPES
        if getattr(config, key) not in existing_field_names
    ]
    items_by_requirement = {
        requirement_id_in(item_body(item)): item
        for item in items
        if requirement_id_in(item_body(item))
    }
    branches = build_branches(tree)
    for branch in branches:
        item = items_by_requirement.get(branch.requirement_id)
        if item is None:
            plan.items_to_create.append(branch)
        elif _is_stale(item, branch, config):
            plan.items_to_update.append((item, branch))
    known = {branch.requirement_id for branch in branches}
    plan.orphans = sorted(set(items_by_requirement) - known)
    return plan


def _apply(plan: BoardPlan, client: GhProjectClient, project: dict | None, fields, config) -> None:
    if project is None:
        project = client.create_project(config.title)
    number, project_id = project["number"], project["id"]
    field_ids = {candidate["name"]: candidate["id"] for candidate in fields}
    for key, data_type in FIELD_TYPES:
        name = getattr(config, key)
        if name in plan.fields_to_create:
            field_ids[name] = client.create_field(number, name, data_type)["id"]
    progress_field_id = field_ids[config.progress_field]
    for branch in plan.items_to_create:
        item = client.create_item(number, branch_title(branch), render_branch_body(branch))
        client.set_text_field(
            project_id, item["id"], progress_field_id, branch_progress_summary(branch)
        )
    for item, branch in plan.items_to_update:
        client.edit_draft(item["content"]["id"], branch_title(branch), render_branch_body(branch))
        client.set_text_field(
            project_id, item["id"], progress_field_id, branch_progress_summary(branch)
        )


def sync_board(
    tree: Tree, client: GhProjectClient, config: BoardConfig, *, dry_run: bool = False
) -> BoardPlan:
    project = find_project(client, config)
    fields = client.list_fields(project["number"]) if project else []
    items = client.list_items(project["number"]) if project else []
    plan = plan_board(tree, project, fields, items, config)
    if not dry_run and not plan.is_empty:
        _apply(plan, client, project, fields, config)
    return plan
