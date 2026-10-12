"""What GitHub and git say about one pull request. A fact that cannot be read is not guessed: the
pull request carries `unreadable_reason` and the rules send it solo."""

from __future__ import annotations

import json
import pathlib
import subprocess
from collections.abc import Callable
from dataclasses import dataclass

from agent_os.product.test_selection.changed_paths import changed_paths
from agent_os.product.tracker.pull_request_checks import verdict_for_rollup
from agent_os.quality.git_snapshots import GitError

GH_FIELDS = (
    "number,title,headRefOid,headRefName,baseRefName,isDraft,state,mergeable,"
    "statusCheckRollup,reviews,createdAt"
)
APPROVED = "APPROVED"
CHANGES_REQUESTED = "CHANGES_REQUESTED"
SETTLING_REVIEW_STATES = frozenset({APPROVED, CHANGES_REQUESTED, "DISMISSED"})


@dataclass(frozen=True)
class PullRequestFacts:
    number: int
    title: str = ""
    head_sha: str = ""
    head_branch: str = ""
    base: str = ""
    is_draft: bool = False
    is_open: bool = True
    mergeable: str = ""
    checks_are_green: bool = False
    checks_problem: str = ""
    approved_on_head: bool = False
    created_at: str = ""
    paths: tuple[str, ...] = ()
    unreadable_reason: str = ""


RunCommand = Callable[[list[str]], subprocess.CompletedProcess]


def run_command_in(repository: pathlib.Path) -> RunCommand:
    def run(arguments: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            arguments, cwd=repository, capture_output=True, text=True, check=False, timeout=120
        )

    return run


def approved_on_head(reviews: list[dict], head_sha: str) -> bool:
    """The newest settling review of each reviewer, on the current head, and at least one approval
    with no change requested standing: an approval of an older head says nothing about this one."""
    latest_by_reviewer: dict[str, dict] = {}
    for review in sorted(reviews, key=lambda row: row.get("submittedAt") or ""):
        if (review.get("state") or "") in SETTLING_REVIEW_STATES:
            latest_by_reviewer[(review.get("author") or {}).get("login") or "?"] = review
    standing = [
        row["state"]
        for row in latest_by_reviewer.values()
        if (row.get("commit") or {}).get("oid") == head_sha or row["state"] == CHANGES_REQUESTED
    ]
    return APPROVED in standing and CHANGES_REQUESTED not in standing


def _checks_problem(rollup: list[dict], number: int) -> tuple[bool, str]:
    if not rollup:
        return False, "no check reported on its head"
    verdict = verdict_for_rollup(number, rollup)
    problems = [*verdict.red, *verdict.pending]
    return verdict.is_green, ", ".join(problems)


def _paths_of(repository: pathlib.Path, run: RunCommand, number: int, head_sha: str, base: str):
    fetched = run(["git", "fetch", "--quiet", "origin", base, f"refs/pull/{number}/head"])
    if fetched.returncode != 0:
        raise GitError(f"git fetch of #{number} failed: {fetched.stderr.strip()}")
    pinned = run(["git", "rev-parse", "FETCH_HEAD"]).stdout.strip()
    if pinned != head_sha:
        raise GitError(f"the head moved while it was read ({pinned[:9]} is not {head_sha[:9]})")
    return tuple(changed_paths(repository, f"origin/{base}", head_sha))


def read_facts(
    repository: pathlib.Path, run: RunCommand, number: int, repo_flags: list[str]
) -> PullRequestFacts:
    viewed = run(["gh", "pr", "view", str(number), *repo_flags, "--json", GH_FIELDS])
    if viewed.returncode != 0:
        return PullRequestFacts(number, unreadable_reason=f"gh: {viewed.stderr.strip()[:200]}")
    try:
        row = json.loads(viewed.stdout)
        head_sha, base = row["headRefOid"], row["baseRefName"]
        checks_green, problem = _checks_problem(row.get("statusCheckRollup") or [], number)
        facts = PullRequestFacts(
            number=number,
            title=row.get("title") or "",
            head_sha=head_sha,
            head_branch=row.get("headRefName") or "",
            base=base,
            is_draft=bool(row.get("isDraft")),
            is_open=row.get("state") == "OPEN",
            mergeable=row.get("mergeable") or "",
            checks_are_green=checks_green,
            checks_problem=problem,
            approved_on_head=approved_on_head(row.get("reviews") or [], head_sha),
            created_at=row.get("createdAt") or "",
        )
    except (ValueError, KeyError, TypeError) as error:
        return PullRequestFacts(number, unreadable_reason=f"unparsable gh answer: {error}")
    if not facts.is_open:
        return facts
    try:
        paths = _paths_of(repository, run, number, head_sha, base)
    except GitError as error:
        return PullRequestFacts(number, unreadable_reason=str(error)[:200])
    return PullRequestFacts(**{**facts.__dict__, "paths": paths})
