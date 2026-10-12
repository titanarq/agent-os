"""`agent-os-integrate land <integration PR>`: steps 6 and 7 of the ADR. Each member merges natively, in
number order, through `safe_merge.sh --group`; then `tree(origin/main)` must equal the tree of the
integration head, or the human is paged. The integration pull request is closed, never merged."""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field

from agent_os.product.integrator.facts import RunCommand
from agent_os.product.integrator.result.verdict import pinned_members_of
from agent_os.product.integrator.round_lock import integration_lock
from agent_os.quality.git_snapshots import GitError

PACKAGE_ROOT = pathlib.Path(__file__).resolve().parents[4]
SAFE_MERGE_SCRIPT = PACKAGE_ROOT / "bin" / "dev" / "safe_merge.sh"
NOTIFY_SCRIPT = PACKAGE_ROOT / "bin" / "notify.sh"
Say = Callable[[str], None]


@dataclass
class LandResult:
    landed: list[int] = field(default_factory=list)
    failure: str = ""
    tree_equal: bool | None = None

    def line(self) -> str:
        members = " ".join(f"#{number}" for number in self.landed) or "none"
        tree = {True: "equal", False: "DIFFERENT", None: "not checked"}[self.tree_equal]
        return f"landed {members}; tree(origin/main) == tree(integration head): {tree}"


def _gh_json(run: RunCommand, arguments: list[str], repo_flags: list[str], what: str) -> dict:
    viewed = run(["gh", "pr", "view", *arguments, *repo_flags])
    if viewed.returncode != 0:
        raise GitError(f"{what} could not be read: {viewed.stderr.strip()}")
    return json.loads(viewed.stdout)


def _tree_of(run: RunCommand, revision: str) -> str:
    answer = run(["git", "rev-parse", f"{revision}^{{tree}}"])
    if answer.returncode != 0:
        raise GitError(f"the tree of {revision} could not be read: {answer.stderr.strip()}")
    return answer.stdout.strip()


def _merge_one_member(
    repository: pathlib.Path, member: int, integration_pr: int, after: str, merge_method: str
) -> subprocess.CompletedProcess:
    arguments = ["bash", str(SAFE_MERGE_SCRIPT), str(repository), str(member)]
    arguments += ["--group", str(integration_pr)] + (["--after", after] if after else [])
    environment = {**os.environ, "GROUP_MERGE_METHOD": merge_method}
    return subprocess.run(
        arguments, capture_output=True, text=True, check=False, env=environment, timeout=300
    )


def _page_human(repository: pathlib.Path, message: str) -> None:
    subprocess.run(
        ["bash", str(NOTIFY_SCRIPT), message], cwd=repository, capture_output=True, check=False
    )


def _close_integration(run, integration_pr, repo_flags, landed: list[int]) -> None:
    listing = "\n".join(f"- #{number}" for number in landed)
    comment = f"Landed, each on its own merge commit:\n{listing}\n\nClosed without merging."
    closed = run(
        ["gh", "pr", "close", str(integration_pr), *repo_flags, "--comment", comment]
        + ["--delete-branch"]
    )
    if closed.returncode != 0:
        raise GitError(f"closing #{integration_pr} failed: {closed.stderr.strip()}")


def land_group(
    repository: pathlib.Path,
    run: RunCommand,
    integration_pr: int,
    repo_flags: list[str],
    merge_method: str,
    say: Say,
) -> LandResult:
    result = LandResult()
    with integration_lock(repository / ".cache"):
        view = _gh_json(
            run, [str(integration_pr), "--json", "body,headRefOid"], repo_flags, "the group"
        )
        members = sorted(pinned_members_of(view["body"] or ""))
        if len(members) < 2:
            raise GitError(f"#{integration_pr} does not list its members and pinned heads")
        after = ""
        for member in members:
            merged = _merge_one_member(repository, member, integration_pr, after, merge_method)
            say((merged.stdout or merged.stderr).strip())
            if merged.returncode != 0:
                result.failure = f"#{member} was not merged; the group stops here"
                return result
            result.landed.append(member)
            after = _gh_json(run, [str(member), "--json", "mergeCommit"], repo_flags, "a merge")[
                "mergeCommit"
            ]["oid"]
        run(["git", "fetch", "--quiet", "origin"])
        base_branch = _gh_json(
            run, [str(integration_pr), "--json", "baseRefName"], repo_flags, "the base"
        )["baseRefName"]
        result.tree_equal = _tree_of(run, f"origin/{base_branch}") == _tree_of(
            run, view["headRefOid"]
        )
        if not result.tree_equal:
            result.failure = "main holds a combination nobody tested"
            _page_human(
                repository, f"integration #{integration_pr}: {result.failure}, trees differ"
            )
            return result
        _close_integration(run, integration_pr, repo_flags, result.landed)
    return result
