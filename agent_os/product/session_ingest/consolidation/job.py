"""The consolidation job issue `consolidate.<node>` (`trigger.py` raises it): what the consolidator reads of it."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass

from agent_os.issues import parse_key_line

KEY_PREFIX = "consolidate."


class NotAConsolidationJob(Exception):
    """The issue is not an open consolidation job: nothing is drafted for it."""


@dataclass(frozen=True)
class ConsolidationJob:
    number: int
    node_id: str
    body: str


def read_job(number: int, repo: str, consolidation_label: str) -> ConsolidationJob:
    completed = subprocess.run(
        ["gh", "issue", "view", str(number), "--repo", repo, "--json", "state,body,labels"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise NotAConsolidationJob(f"cannot read issue #{number}: {completed.stderr.strip()}")
    issue = json.loads(completed.stdout)
    key = parse_key_line(issue.get("body"))
    if issue.get("state", "").upper() != "OPEN":
        raise NotAConsolidationJob(f"issue #{number} is not open")
    if not key or not key.startswith(KEY_PREFIX):
        raise NotAConsolidationJob(
            f"issue #{number} has no `<!-- key: {KEY_PREFIX}<node> -->` line"
        )
    if consolidation_label not in {label["name"] for label in issue.get("labels", [])}:
        raise NotAConsolidationJob(
            f"issue #{number} does not carry the `{consolidation_label}` label"
        )
    return ConsolidationJob(number, key[len(KEY_PREFIX) :], issue["body"])
