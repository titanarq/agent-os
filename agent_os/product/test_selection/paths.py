"""How a manifest entry holds a path: equal to it, or under it when the entry is a directory."""

from __future__ import annotations

from collections.abc import Iterable


def normalize_entry(entry: str) -> str:
    return entry.strip().removeprefix("./").rstrip("/")


def entry_holds_path(entry: str, path: str) -> bool:
    normalized = normalize_entry(entry)
    return bool(normalized) and (path == normalized or path.startswith(normalized + "/"))


def any_entry_holds_path(entries: Iterable[str], path: str) -> bool:
    return any(entry_holds_path(entry, path) for entry in entries)
