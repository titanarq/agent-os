"""The defects a manifest has by itself, one line each, each saying what to do."""

from __future__ import annotations

import pathlib
from collections import Counter

from agent_os.product.test_selection.manifest import Manifest
from agent_os.product.test_selection.paths import any_entry_holds_path, normalize_entry


def _duplicated(kind: str, identifiers: list[str], manifest: Manifest) -> list[str]:
    return [
        f"{manifest.label}: {kind} id `{identifier}` is declared {count} times: keep one"
        for identifier, count in Counter(identifiers).items()
        if count > 1
    ]


def _structure_defects(manifest: Manifest) -> list[str]:
    defects = _duplicated("group", [group.id for group in manifest.groups], manifest)
    defects += _duplicated("integration", [item.id for item in manifest.integration], manifest)
    group_ids = {group.id for group in manifest.groups}
    for item in manifest.integration:
        if len(item.sides) < 2:
            defects.append(
                f"{manifest.label}: integration `{item.id}` has fewer than two sides: "
                "list the two or more groups it lives between"
            )
        for side in item.sides:
            if side not in group_ids:
                defects.append(
                    f"{manifest.label}: integration `{item.id}` names side `{side}`, "
                    "which is not a group id: fix the id or add the group"
                )
    return defects


def _mapped_entries(manifest: Manifest) -> list[str]:
    entries = list(manifest.settings.always)
    for group in manifest.groups:
        entries += [*group.covers, *group.tests]
    for item in manifest.integration:
        entries += item.tests
    return entries


def _missing_path_defects(manifest: Manifest, repository_root: pathlib.Path) -> list[str]:
    missing = {
        entry
        for entry in _mapped_entries(manifest)
        if not (repository_root / normalize_entry(entry)).exists()
    }
    return [
        f"{manifest.label}: `{entry}` does not exist: remove it or correct the path"
        for entry in sorted(missing)
    ]


def test_files_of(manifest: Manifest, repository_root: pathlib.Path) -> list[str]:
    found: set[str] = set()
    for pattern in manifest.settings.test_globs:
        found |= {
            path.relative_to(repository_root).as_posix()
            for path in repository_root.glob(pattern)
            if path.is_file()
        }
    return sorted(found)


def _unmapped_test_defects(manifest: Manifest, repository_root: pathlib.Path) -> list[str]:
    mapped_tests = list(manifest.settings.always)
    for group in manifest.groups:
        mapped_tests += group.tests
    for item in manifest.integration:
        mapped_tests += item.tests
    return [
        f"`{test_file}` is mapped by no group: add it to the group of the use case or module "
        f"it verifies in `{manifest.label}`"
        for test_file in test_files_of(manifest, repository_root)
        if not any_entry_holds_path(mapped_tests, test_file)
    ]


def check_manifest(manifest: Manifest, repository_root: pathlib.Path) -> list[str]:
    return [
        *_structure_defects(manifest),
        *_missing_path_defects(manifest, repository_root),
        *_unmapped_test_defects(manifest, repository_root),
    ]
