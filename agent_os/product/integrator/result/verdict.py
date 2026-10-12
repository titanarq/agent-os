"""`agent-os-integrate result <integration PR>`: one verdict for the round, `passed`,
`evict #N` or `solo`. No bisection: at most one eviction per round (the ADR, "When the group fails")."""

from __future__ import annotations

import json
import pathlib
import re
from dataclasses import dataclass

from agent_os.product.integrator.facts import RunCommand, read_facts
from agent_os.product.integrator.plan import TestSelectionInputs, own_plan
from agent_os.product.integrator.result.attribution import (
    member_to_evict,
    read_failing_test_ids,
)
from agent_os.product.integrator.result.waiting import wait_for_checks
from agent_os.quality.git_snapshots import GitError

MEMBER_ROW = re.compile(r"^- #(?P<number>\d+) at `(?P<head>[0-9a-f]+)`$", re.MULTILINE)
REBUILT_MARKER = re.compile(
    r"^Rebuilt without #(?P<number>\d+) after a failed round\.$", re.MULTILINE
)


@dataclass(frozen=True)
class Verdict:
    kind: str  # "passed" | "evict" | "solo"
    member: int | None = None
    reason: str = ""

    def line(self) -> str:
        if self.kind == "evict":
            return f"evict #{self.member}"
        return self.kind if not self.reason else f"{self.kind}: {self.reason}"


def pinned_members_of(body: str) -> dict[int, str]:
    return {int(row["number"]): row["head"] for row in MEMBER_ROW.finditer(body)}


def _read_integration_body(run: RunCommand, pull_request: int, repo_flags: list[str]) -> str:
    viewed = run(["gh", "pr", "view", str(pull_request), *repo_flags, "--json", "body"])
    if viewed.returncode != 0:
        raise GitError(f"the integration pull request could not be read: {viewed.stderr.strip()}")
    return json.loads(viewed.stdout).get("body") or ""


def decide_round(
    repository: pathlib.Path,
    run: RunCommand,
    pull_request: int,
    repo_flags: list[str],
    inputs: TestSelectionInputs,
    ci_wait_max_minutes: int,
    summary_index_path: pathlib.Path | None,
) -> Verdict:
    body = _read_integration_body(run, pull_request, repo_flags)
    pinned = pinned_members_of(body)
    if len(pinned) < 2:
        raise GitError(f"#{pull_request} does not list its members and pinned heads")
    reading = wait_for_checks(repository, pull_request, ci_wait_max_minutes)
    if reading.outcome == 0:
        return Verdict("passed")
    if not reading.is_a_test_failure:
        return Verdict("solo", reason=f"a timeout or an infrastructure red: {reading.line}")
    return _attribute(repository, run, repo_flags, inputs, pinned, body, summary_index_path)


def _attribute(repository, run, repo_flags, inputs, pinned, body, summary_index_path) -> Verdict:
    if summary_index_path is None:
        return Verdict("solo", reason="red, and no summary index of the run was given")
    plans = {}
    for number, head in pinned.items():
        facts = read_facts(repository, run, number, repo_flags)
        if facts.unreadable_reason or facts.head_sha != head:
            return Verdict("solo", reason=f"#{number} cannot be read at its pinned head")
        plans[number] = own_plan(inputs, facts.paths)
    member, why = member_to_evict(read_failing_test_ids(summary_index_path), plans)
    if member is None:
        return Verdict("solo", reason=why)
    if REBUILT_MARKER.search(body):
        return Verdict("solo", reason=f"the rebuilt group failed again, implicating #{member}")
    return Verdict("evict", member)
