"""The two `gh` reads the in-works command needs: open issues and open pull requests.

A `gh` that is missing, refuses, or answers something that is not a JSON list is an
`InWorksError` carrying the reason, never an empty listing: an empty listing would read as
"nothing is in works".
"""

from __future__ import annotations

import json
import subprocess

LISTING_LIMIT = "1000"


class InWorksError(Exception):
    """GitHub could not be read, so no honest answer exists."""


def _list_open(kind: str, repository: str, fields: str) -> list[dict]:
    command = ["gh", kind, "list", "--repo", repository, "--state", "open"]
    command += ["--json", fields, "--limit", LISTING_LIMIT]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError as error:
        raise InWorksError("`gh` is not on PATH; in-works needs the GitHub CLI") from error
    if completed.returncode != 0:
        raise InWorksError(f"`gh {kind} list` failed: {completed.stderr.strip()}")
    try:
        rows = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise InWorksError(f"`gh {kind} list` did not answer JSON") from error
    if not isinstance(rows, list):
        raise InWorksError(f"`gh {kind} list` did not answer a list")
    return rows


def open_issues(repository: str) -> list[dict]:
    return _list_open("issue", repository, "number,body,labels")


def open_pull_requests(repository: str) -> list[dict]:
    return _list_open("pr", repository, "number,body,files")
