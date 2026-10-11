"""What a branch changed in the manifest itself, read as a diff of the parsed manifests."""

from __future__ import annotations

import pathlib
from dataclasses import dataclass

from agent_os.product.test_selection.changed_paths import run_git
from agent_os.product.test_selection.manifest import Manifest, parse_manifest
from agent_os.product.test_selection.paths import entry_holds_path
from agent_os.quality.git_snapshots import GitError


@dataclass(frozen=True)
class ManifestChange:
    # The repository paths that make up the manifest, so they are not read as unmapped code.
    files: frozenset[str]
    # Group ids whose entry was added or changed (an integration that changed counts its sides).
    changed_group_ids: frozenset[str]
    # `exempt` or `always` changed: it widens what no selection looks at.
    widens_selection: bool


def manifest_files_changed(changed_paths: list[str], manifest_path: str) -> bool:
    return any(entry_holds_path(manifest_path, path) for path in changed_paths)


def manifest_at_revision(
    repository: pathlib.Path, revision: str, manifest_path: str
) -> Manifest | None:
    """The manifest as the revision had it, or `None` when the revision had none."""
    listed = run_git(
        repository, "ls-tree", "-r", "-z", "--name-only", revision, "--", manifest_path
    )
    names = [name.decode() for name in listed.split(b"\0") if name]
    if not names:
        return None
    is_folder = names != [manifest_path]
    prefix = manifest_path.rstrip("/") + "/"
    documents = {}
    for name in names:
        if is_folder and not name.endswith(".yaml"):
            continue
        key = name.removeprefix(prefix) if is_folder else name
        try:
            documents[key] = run_git(repository, "show", f"{revision}:{name}").decode("utf-8")
        except GitError as error:
            raise GitError(f"cannot read {name} at {revision}: {error}") from error
    return parse_manifest(documents, is_folder=is_folder, label=manifest_path)


def _files_of(repository: pathlib.Path, revision: str | None, manifest_path: str) -> set[str]:
    command = ("ls-tree", "-r", "-z", "--name-only", revision) if revision else ("ls-files", "-z")
    output = run_git(repository, *command, "--", manifest_path)
    return {name.decode() for name in output.split(b"\0") if name}


def describe_manifest_change(
    repository: pathlib.Path, merge_base: str, head: Manifest, manifest_path: str
) -> ManifestChange:
    before = manifest_at_revision(repository, merge_base, manifest_path)
    files = _files_of(repository, merge_base, manifest_path) | _files_of(
        repository, None, manifest_path
    )
    if before is None:
        return ManifestChange(frozenset(files), frozenset(group.id for group in head.groups), False)
    groups_before = {group.id: group for group in before.groups}
    changed = {group.id for group in head.groups if groups_before.get(group.id) != group}
    integrations_before = {item.id: item for item in before.integration}
    for item in head.integration:
        if integrations_before.get(item.id) != item:
            changed |= set(item.sides)
    widens = (
        before.settings.exempt != head.settings.exempt
        or before.settings.always != head.settings.always
    )
    return ManifestChange(frozenset(files), frozenset(changed), widens)
