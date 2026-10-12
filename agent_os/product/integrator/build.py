"""`agent-os-integrate build`: steps 1 to 4 of the ADR. Take the lock, fetch, record the base,
merge each member's pinned head into a throwaway worktree, run the pre-flight, push
`integration/<UTC stamp>` and open the integration pull request. It never resolves a conflict and
never edits a pull request's code; with `dry_run` it prints the commands and changes nothing."""

from __future__ import annotations

import pathlib
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from agent_os.product.integrator.candidates import reason_not_a_candidate
from agent_os.product.integrator.facts import PullRequestFacts, RunCommand, read_facts
from agent_os.product.integrator.preflight import describe_failure, run_preflight
from agent_os.product.integrator.round_lock import integration_lock
from agent_os.product.tracker.pull_request_checks import INTEGRATION_BRANCH_PREFIX
from agent_os.quality.git_snapshots import GitError

Say = Callable[[str], None]
MINIMUM_GROUP = 2


@dataclass
class BuildResult:
    pull_request: int | None = None
    base: str = ""
    members: tuple[int, ...] = ()
    left_solo: dict[int, str] = field(default_factory=dict)
    failure: str = ""

    def line(self) -> str:
        members = " ".join(f"#{number}" for number in self.members)
        return f"integration PR #{self.pull_request} base {self.base} members {members}"


def integration_title(members: Sequence[int]) -> str:
    return "integration: " + " ".join(f"#{number}" for number in members)


def integration_body(
    members: Sequence[int], pinned: dict[int, str], base: str, evicted: Sequence[int] = ()
) -> str:
    rows = "\n".join(f"- #{number} at `{pinned[number]}`" for number in members)
    rebuilt = "".join(f"\nRebuilt without #{number} after a failed round.\n" for number in evicted)
    return (
        f"The integrator's proof of a group of ready pull requests, built on `{base}`. It is never "
        f"merged: each member lands on its own once this head's checks are all SUCCESS.\n\n"
        f"Members and their pinned heads:\n{rows}\n{rebuilt}"
    )


def _checked(run: RunCommand, arguments: list[str], what: str) -> str:
    outcome = run(arguments)
    if outcome.returncode != 0:
        raise GitError(f"{what} failed: {(outcome.stderr or outcome.stdout).strip()}")
    return outcome.stdout.strip()


def _merge_members(
    run_in_tree: RunCommand, members: Sequence[int], pinned: dict[int, str]
) -> dict[int, str]:
    """Merge in number order; a conflicting one is aborted and returned with its reason."""
    conflicted: dict[int, str] = {}
    for number in members:
        merged = run_in_tree(
            ["git", "merge", "--no-ff", "-m", f"Merge pull request #{number}", pinned[number]]
        )
        if merged.returncode != 0:
            run_in_tree(["git", "merge", "--abort"])
            conflicted[number] = "its merge into the group conflicts"
    return conflicted


def _print_plan_of_commands(say: Say, base_branch: str, members: Sequence[int], pinned) -> None:
    commands = [
        f"git fetch origin {base_branch}",
        f"git worktree add -b {INTEGRATION_BRANCH_PREFIX}<stamp> <tree> origin/{base_branch}",
        *(f"git merge --no-ff {pinned[number]}   # #{number}" for number in members),
        "ruff check . && ruff format --check .",
        "python -m agent_os.quality --base <base> --root <tree>",
        "agent-os-tests check",
        f"git push origin {INTEGRATION_BRANCH_PREFIX}<stamp>",
        f"gh pr create --base {base_branch} --title '{integration_title(members)}'",
    ]
    say("dry run, nothing is changed; the commands are:")
    for command in commands:
        say(f"  {command}")


def _read_members(
    repository: pathlib.Path,
    run: RunCommand,
    pull_requests: Sequence[int],
    default_branch: str,
    repo_flags: list[str],
) -> tuple[dict[int, PullRequestFacts], dict[int, str]]:
    kept: dict[int, PullRequestFacts] = {}
    left: dict[int, str] = {}
    for number in sorted(dict.fromkeys(pull_requests)):
        facts = read_facts(repository, run, number, repo_flags)
        reason = reason_not_a_candidate(facts, default_branch)
        if reason:
            left[number] = reason
        else:
            kept[number] = facts
    return kept, left


def build_integration(
    repository: pathlib.Path,
    run: RunCommand,
    pull_requests: Sequence[int],
    default_branch: str,
    repo_flags: list[str],
    say: Say,
    *,
    dry_run: bool,
    without: Sequence[int] = (),
) -> BuildResult:
    result = BuildResult()
    kept, result.left_solo = _read_members(
        repository,
        run,
        [number for number in pull_requests if number not in without],
        default_branch,
        repo_flags,
    )
    for number in without:
        result.left_solo[number] = "evicted after the group's failed round"
    members = tuple(kept)
    pinned = {number: facts.head_sha for number, facts in kept.items()}
    if len(members) < MINIMUM_GROUP:
        result.failure = "fewer than two members can be integrated"
        return result
    if dry_run:
        _print_plan_of_commands(say, default_branch, members, pinned)
        result.members = members
        return result
    with integration_lock(repository / ".cache"):
        return _build_locked(
            repository, run, kept, default_branch, repo_flags, result, pinned, without
        )


def _build_locked(
    repository, run, kept, default_branch, repo_flags, result, pinned, without
) -> BuildResult:
    _checked(run, ["git", "fetch", "--quiet", "origin", default_branch], "fetching the base")
    base_sha = _checked(run, ["git", "rev-parse", f"origin/{default_branch}"], "reading the base")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    branch = f"{INTEGRATION_BRANCH_PREFIX}{stamp}"
    tree = repository / ".cache" / "integrator" / "worktrees" / stamp
    _checked(run, ["git", "worktree", "add", "-q", "-b", branch, str(tree), base_sha], "worktree")
    pushed = False

    def run_in_tree(arguments: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            arguments, cwd=tree, capture_output=True, text=True, check=False, timeout=600
        )

    try:
        result.left_solo |= _merge_members(run_in_tree, tuple(kept), pinned)
        members = tuple(number for number in kept if number not in result.left_solo)
        result.base, result.members = base_sha, members
        if len(members) < MINIMUM_GROUP:
            result.failure = "fewer than two members survived the merges"
            return result
        paths_by_member = {number: kept[number].paths for number in members}
        failure = run_preflight(run_in_tree, tree, base_sha)
        if failure:
            result.failure = describe_failure(failure, paths_by_member)
            return result
        _checked(run_in_tree, ["git", "push", "origin", branch], "the push")
        pushed = True
        created = _checked(
            run_in_tree,
            [
                "gh",
                "pr",
                "create",
                *repo_flags,
                "--base",
                default_branch,
                "--head",
                branch,
                "--title",
                integration_title(members),
                "--body",
                integration_body(members, pinned, base_sha, without),
            ],
            "opening the integration pull request",
        )
        result.pull_request = int(created.rstrip("/").rsplit("/", 1)[-1])
        return result
    finally:
        run(["git", "worktree", "remove", "--force", str(tree)])
        if not pushed:
            run(["git", "branch", "-D", branch])
