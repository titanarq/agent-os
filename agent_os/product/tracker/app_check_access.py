"""Whether a GitHub App may read the CI checks of a pull request, and the one line that says so.

A pull request's checks are two permissions of the App that asks: `Checks: read` for the check
runs and `Commit statuses: read` for the legacy statuses. `gh pr list --json statusCheckRollup`
(what `issues.py move N review` runs) and `gh pr checks` (what the validator and the control plane
run) need both, and an App without them is answered "Resource not accessible by integration" --
GraphQL's wording on one path, a bare 403 on the REST one. Nothing in that sentence says which
permission is missing or where to grant it, so the doctor probes both before the first run and
`move` translates the refusal when it meets it anyway (docs/ADOPTION.md step 14).
"""

from __future__ import annotations

import os
import pathlib
import subprocess
from collections.abc import Callable
from dataclasses import dataclass

from agent_os.cli import agent_os_python

CHECKS_PERMISSION = "Checks: read"
COMMIT_STATUSES_PERMISSION = "Commit statuses: read"
# What each permission opens, on the default branch's head: `HEAD` names that commit for REST
# without asking the repository which branch is the default one.
PROBED_ENDPOINTS = (
    (CHECKS_PERMISSION, "check-runs"),
    (COMMIT_STATUSES_PERMISSION, "status"),
)
PERMISSION_REFUSAL_MARKER = "resource not accessible by integration"

REMEDY = (
    "grant them under the App's Permissions & events > Repository permissions, then accept the "
    "new permissions on the installation (an organization owner approves the request); "
    "docs/ADOPTION.md step 14"
)


@dataclass(frozen=True)
class CheckAccess:
    lacking_permissions: tuple[str, ...]
    # The first failure that was not a permission refusal (a 404, no network): nothing can be said
    # about the permissions behind it.
    unreadable_reason: str | None


def is_permission_refusal(message: str) -> bool:
    return PERMISSION_REFUSAL_MARKER in message.lower()


def probe_check_access(
    repo: str, run_gh_as_app: Callable[..., subprocess.CompletedProcess]
) -> CheckAccess:
    """Asks `repo` for the check runs and the statuses of its default branch's head, as the App
    `run_gh_as_app` signs as, and names every permission the answers say it lacks. Read-only."""
    lacking = []
    unreadable_reason = None
    for permission, endpoint in PROBED_ENDPOINTS:
        result = run_gh_as_app("api", f"repos/{repo}/commits/HEAD/{endpoint}")
        if result.returncode == 0:
            continue
        message = " ".join((result.stderr or result.stdout).split())
        if is_permission_refusal(message):
            lacking.append(permission)
        elif unreadable_reason is None:
            unreadable_reason = message or f"gh api exited {result.returncode}"
    return CheckAccess(tuple(lacking), unreadable_reason)


def _one_line(message: str) -> str:
    return " ".join(message.split())


def _mint_installation_token(app_slug: str, host_root: pathlib.Path) -> tuple[str | None, str]:
    """`(token, why not)`: the App's installation token, from the same `agent_os.gh_app_token`
    every role mints with (cached under the host's `.cache/` for the hour it lives), or None and
    the reason it could not be minted."""
    minted = subprocess.run(
        [agent_os_python(), "-m", "agent_os.gh_app_token", "--app", app_slug],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "AGENT_OS_HOST_ROOT": str(host_root)},
    )
    token = minted.stdout.strip()
    if minted.returncode == 0 and token:
        return token, ""
    return None, _one_line(minted.stderr or f"exit {minted.returncode} with no token")


def _describe_one_app(
    repo: str, host_root: pathlib.Path, app_slug: str, roles: list[str]
) -> tuple[str, bool] | None:
    """`(what is wrong with `app_slug` reading checks, whether a permission is to blame)`, or None
    when nothing is."""
    subject = f"{app_slug} ({'/'.join(roles)})"
    token, why_not = _mint_installation_token(app_slug, host_root)
    if token is None:
        return f"{subject}: no installation token -- {why_not}", False

    def run_gh_as_app(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "GH_TOKEN": token},
        )

    access = probe_check_access(repo, run_gh_as_app)
    if access.lacking_permissions:
        return f"{subject} needs {' and '.join(access.lacking_permissions)}", True
    if access.unreadable_reason:
        return f"{subject}: could not tell -- {_one_line(access.unreadable_reason)}", False
    return None


def describe_check_access_of_apps(
    repo: str, host_root: pathlib.Path, roles_by_app: dict[str, list[str]]
) -> tuple[bool, str]:
    """`(ok, one line)` for the doctor: every App of `roles_by_app` (slug -> the roles that sign as
    it and read checks) probed with its own token. The remedy closes the line when a permission
    is what is missing."""
    findings = [
        finding
        for app_slug, roles in roles_by_app.items()
        if (finding := _describe_one_app(repo, host_root, app_slug, roles))
    ]
    if not findings:
        return True, f"{sorted(roles_by_app)} may read check runs and commit statuses"
    line = "; ".join(text for text, _ in findings)
    if any(permission_to_blame for _, permission_to_blame in findings):
        line += f" -- {REMEDY}"
    return False, line


def both_permissions_refused_line(refused_action: str) -> str:
    """The one line `refused_action` (`move #7 review refused`) exits with when the App that
    signs the run is refused the checks. GitHub's own refusal is reduced to a few words: it names
    no permission, and the permissions are what the reader has to go and grant."""
    return (
        f"{refused_action}: the GitHub App this run signs as cannot read pull request checks "
        f"(GitHub answered: Resource not accessible by integration). It needs {CHECKS_PERMISSION} and {COMMIT_STATUSES_PERMISSION}: "
        f"{REMEDY}. `agent-os-doctor` tests it."
    )


def read_open_pull_requests_with_checks(
    repo: str, read_json: Callable, *, refused_action: str
) -> list[dict]:
    """The open pull requests with their check rollup, through `read_json` (`issues.gh_json`).
    A refusal for lack of permission exits with `both_permissions_refused_line`; any other `gh`
    failure goes up as it came."""
    try:
        pull_requests = read_json(
            "pr", "list", "--repo", repo, "--state", "open", "--limit", "200",
            "--json", "number,body,statusCheckRollup",
        )  # fmt: skip
    except SystemExit as failure:
        if not is_permission_refusal(str(failure.code)):
            raise
        raise SystemExit(both_permissions_refused_line(refused_action)) from failure
    return pull_requests or []
