"""The plan of a branch: a pure function of the manifest and what the branch changed."""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from agent_os.product.test_selection.manifest import Manifest
from agent_os.product.test_selection.manifest_changes import ManifestChange
from agent_os.product.test_selection.paths import any_entry_holds_path

SELECTION_IS_OFF = "test selection is off"
MAX_UNMAPPED_PATHS_NAMED = 10


@dataclass(frozen=True)
class TestPlan:
    __test__ = False  # not a pytest class, whatever its name starts with

    mode: Literal["selected", "full"]
    reason: str
    groups: tuple[str, ...] = ()
    tests: tuple[str, ...] = ()
    unmapped_paths: tuple[str, ...] = ()

    def summary(self) -> str:
        if self.mode == "full":
            return f"mode: full ({self.reason})"
        lines = [f"mode: selected ({self.reason})", f"groups: {', '.join(self.groups) or '-'}"]
        return "\n".join([*lines, *(f"  {test}" for test in self.tests)])


def full_plan_because_off() -> TestPlan:
    return TestPlan("full", SELECTION_IS_OFF)


def _groups_selected_by_path(manifest: Manifest, path: str) -> set[str]:
    return {
        group.id
        for group in manifest.groups
        if any_entry_holds_path(group.covers, path) or any_entry_holds_path(group.tests, path)
    }


def _groups_selected_by_node(
    manifest: Manifest, node_id: str, tree_ancestors: Mapping[str, Sequence[str]]
) -> set[str]:
    family = {node_id, *tree_ancestors.get(node_id, ())}
    return {group.id for group in manifest.groups if family & set(group.nodes)}


def _full(reason: str, unmapped: Sequence[str] = ()) -> TestPlan:
    return TestPlan("full", reason, unmapped_paths=tuple(unmapped))


def plan_tests(
    manifest: Manifest,
    changed_paths: Collection[str],
    node_ids_changed: Mapping[str, str],
    tree_ancestors: Mapping[str, Sequence[str]],
    manifest_change: ManifestChange | None = None,
) -> TestPlan:
    """`node_ids_changed` maps the changed paths that are node files to their node id, and
    `tree_ancestors` maps a node id to the ids of its ancestors by `parent`."""
    if manifest_change is not None and manifest_change.widens_selection:
        return _full(
            "`exempt` or `always` changed in the manifest: it widens what no selection sees"
        )
    selected: set[str] = set()
    if manifest_change is not None:
        selected |= manifest_change.changed_group_ids
    unmapped: list[str] = []
    for path in sorted(changed_paths):
        if manifest_change is not None and path in manifest_change.files:
            continue
        by_path = _groups_selected_by_path(manifest, path)
        if path in node_ids_changed:
            by_path |= _groups_selected_by_node(manifest, node_ids_changed[path], tree_ancestors)
        selected |= by_path
        if not by_path and not any_entry_holds_path(manifest.settings.exempt, path):
            unmapped.append(path)
    if unmapped:
        named = ", ".join(unmapped[:MAX_UNMAPPED_PATHS_NAMED])
        more = len(unmapped) - MAX_UNMAPPED_PATHS_NAMED
        suffix = f" and {more} more" if more > 0 else ""
        return _full(f"no group covers {named}{suffix}", unmapped)
    return _selected_plan(manifest, selected, len(changed_paths))


def _selected_plan(manifest: Manifest, selected: set[str], changed_count: int) -> TestPlan:
    tests: list[str] = []
    for group in manifest.groups:
        if group.id in selected:
            tests += group.tests
    for item in manifest.integration:
        if selected & set(item.sides):
            tests += item.tests
    tests += manifest.settings.always
    unique_tests = tuple(dict.fromkeys(tests))
    ordered_groups = tuple(group.id for group in manifest.groups if group.id in selected)
    reason = f"{len(ordered_groups)} group(s) selected by {changed_count} changed path(s)"
    return TestPlan("selected", reason, ordered_groups, unique_tests)
