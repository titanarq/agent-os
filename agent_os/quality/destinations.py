"""Where the entries of a full folder could go: a hint printed under the violation, never a rule.

A worker blocked on a folder over its entry limit used to be told only the count. The files of such
a folder usually share a stem (`test_open_pr_*`, `worker_publication_*`), and a group of them is the
natural content of a new subfolder."""

from __future__ import annotations

import posixpath
from collections import defaultdict
from collections.abc import Collection

from agent_os.quality.ratchet import FOLDER_TOO_FULL, Violation

MINIMUM_FILES_TO_PROPOSE_A_GROUP = 2


def _stem_prefix(file_name: str) -> str:
    """`test_open_pr_quality.py` -> `test_open`: the first two words of the stem, or the first one
    when it has only two."""
    stem = file_name.rsplit(".", 1)[0]
    words = stem.replace("-", "_").split("_")
    return "_".join(words[:2]) if len(words) > 2 else words[0]


def _direct_files_of(folder: str, tracked_paths: Collection[str]) -> list[str]:
    return sorted(
        path_name
        for path_name in (
            posixpath.relpath(path, folder or ".")
            for path in tracked_paths
            if posixpath.dirname(path) == folder
        )
    )


def destination_hint(violation: Violation, tracked_paths: Collection[str]) -> str:
    """One indented line naming files of the violating folder that could move and where; empty when
    the violation is not a full folder."""
    if violation.kind != FOLDER_TOO_FULL:
        return ""
    folder = violation.path
    files_by_prefix: dict[str, list[str]] = defaultdict(list)
    for file_name in _direct_files_of(folder, tracked_paths):
        files_by_prefix[_stem_prefix(file_name)].append(file_name)
    groups = [
        (prefix, names)
        for prefix, names in files_by_prefix.items()
        if len(names) >= MINIMUM_FILES_TO_PROPOSE_A_GROUP
    ]
    shown_folder = folder or "."
    if not groups:
        return (
            f"  hint: {shown_folder}: no files share a name stem; make a subfolder named after one "
            "concern of the folder and move the files of that concern into it"
        )
    prefix, names = max(groups, key=lambda group: len(group[1]))
    destination = posixpath.join(folder, prefix)
    shown_names = ", ".join(names[:6]) + (", ..." if len(names) > 6 else "")
    return (
        f"  hint: {shown_folder}: move {len(names)} files sharing the stem `{prefix}` "
        f"({shown_names}) into a new subfolder {destination}/ (git mv, then fix imports and paths)"
    )
