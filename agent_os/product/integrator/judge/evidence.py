"""The facts of the index that are not in the plan: the title of the issue a pull request closes and
the hunk headers of the symbols it changes. Read with `gh` and `git`; a fact that cannot be read is
left empty, and the judge reads the index without it."""

from __future__ import annotations

import json
import pathlib

from agent_os.product.integrator.facts import RunCommand
from agent_os.product.integrator.judge.index import MAX_HUNK_HEADER_LINES

HUNK_MARK = "@@"


def closed_issue_title(run: RunCommand, number: int, repo_flags: list[str]) -> str:
    viewed = run(
        ["gh", "pr", "view", str(number), *repo_flags, "--json", "closingIssuesReferences"]
    )
    if viewed.returncode != 0:
        return ""
    try:
        references = json.loads(viewed.stdout).get("closingIssuesReferences") or []
        issue = references[0]["number"] if references else None
    except (ValueError, KeyError, TypeError, AttributeError):
        return ""
    if issue is None:
        return ""
    issue_view = run(["gh", "issue", "view", str(issue), *repo_flags, "--json", "title"])
    if issue_view.returncode != 0:
        return ""
    try:
        return str(json.loads(issue_view.stdout).get("title") or "")
    except (ValueError, AttributeError):
        return ""


def hunk_headers(
    repository: pathlib.Path, run: RunCommand, base: str, head_sha: str
) -> tuple[tuple[str, ...], int]:
    """`(headers, how many were left out)`: per hunk of `base...head` its file and its `@@` line,
    which names the function or class the hunk sits in, at most `MAX_HUNK_HEADER_LINES`."""
    diff = run(
        ["git", "-C", str(repository), "diff", "-U0", "--no-renames", f"{base}...{head_sha}"]
    )
    if diff.returncode != 0:
        return (), 0
    lines, current_file = [], ""
    for line in diff.stdout.splitlines():
        if line.startswith("+++ "):
            current_file = line[4:].removeprefix("b/")
        elif line.startswith("--- a/") and not current_file:
            current_file = line[6:]
        elif line.startswith(HUNK_MARK):
            lines.append(f"{current_file}: {line}")
    return tuple(lines[:MAX_HUNK_HEADER_LINES]), max(0, len(lines) - MAX_HUNK_HEADER_LINES)
