"""The ratchet itself: pure functions from two snapshots of a repository to violations.

A new file or folder must comply with the limits. One that already exists may be over a limit but
never further over than it was on the base: a file may not grow, a folder may not gain an entry.
Moving the code out of an offender is therefore always allowed and adding to it never is."""

from __future__ import annotations

from collections.abc import Callable, Collection, Iterable
from dataclasses import dataclass

FILE_TOO_LONG = "file-too-long"
FOLDER_TOO_FULL = "folder-too-full"


@dataclass(frozen=True)
class RepositorySnapshot:
    """The tracked paths of one revision and a way to count the lines of one of them."""

    tracked_paths: frozenset[str]
    count_lines_of: Callable[[str], int]


@dataclass(frozen=True)
class Limits:
    max_entries_per_folder: int
    max_lines_per_file: int


@dataclass(frozen=True)
class Violation:
    kind: str
    path: str
    measured: int
    limit: int
    measured_on_base: int | None

    def describe(self) -> str:
        subject = "lines" if self.kind == FILE_TOO_LONG else "entries"
        shown_path = self.path or "."
        if self.measured_on_base is None:
            return f"{shown_path}: new, {self.measured} {subject} (limit {self.limit})"
        return (
            f"{shown_path}: {self.measured} {subject}, was {self.measured_on_base} on the base "
            f"(limit {self.limit}; an existing one may not get worse)"
        )


def is_excluded(path: str, excluded_paths: Collection[str]) -> bool:
    return any(
        path == excluded or path.startswith(excluded + "/")
        for excluded in (entry.rstrip("/") for entry in excluded_paths)
    )


def entries_per_folder(
    tracked_paths: Iterable[str], excluded_paths: Collection[str]
) -> dict[str, int]:
    """Direct entries (files and subfolders) of every folder; `""` is the root. An excluded path
    still occupies one entry in its parent, since it shows in a listing, but is never entered."""
    entries_of_folder: dict[str, set[str]] = {}
    for tracked_path in tracked_paths:
        parts = tracked_path.split("/")
        for depth in range(len(parts)):
            entry = "/".join(parts[: depth + 1])
            folder = "/".join(parts[:depth])
            entries_of_folder.setdefault(folder, set()).add(entry)
            if is_excluded(entry, excluded_paths):
                break
    return {
        folder: len(entries)
        for folder, entries in entries_of_folder.items()
        if not is_excluded(folder, excluded_paths)
    }


def _worsened(measured: int, limit: int, measured_on_base: int | None) -> bool:
    if measured <= limit:
        return False
    return measured_on_base is None or measured > measured_on_base


def _folder_violations(
    base: RepositorySnapshot,
    head: RepositorySnapshot,
    limits: Limits,
    excluded_paths: Collection[str],
) -> list[Violation]:
    entries_on_base = entries_per_folder(base.tracked_paths, excluded_paths)
    violations = []
    for folder, measured in sorted(entries_per_folder(head.tracked_paths, excluded_paths).items()):
        on_base = entries_on_base.get(folder)
        if _worsened(measured, limits.max_entries_per_folder, on_base):
            violations.append(
                Violation(FOLDER_TOO_FULL, folder, measured, limits.max_entries_per_folder, on_base)
            )
    return violations


def _file_violations(
    base: RepositorySnapshot,
    head: RepositorySnapshot,
    limits: Limits,
    excluded_paths: Collection[str],
) -> list[Violation]:
    violations = []
    for path in sorted(head.tracked_paths):
        if is_excluded(path, excluded_paths):
            continue
        measured = head.count_lines_of(path)
        if measured <= limits.max_lines_per_file:
            continue
        on_base = base.count_lines_of(path) if path in base.tracked_paths else None
        if _worsened(measured, limits.max_lines_per_file, on_base):
            violations.append(
                Violation(FILE_TOO_LONG, path, measured, limits.max_lines_per_file, on_base)
            )
    return violations


def find_violations(
    base: RepositorySnapshot,
    head: RepositorySnapshot,
    limits: Limits,
    excluded_paths: Collection[str],
) -> list[Violation]:
    return _folder_violations(base, head, limits, excluded_paths) + _file_violations(
        base, head, limits, excluded_paths
    )
