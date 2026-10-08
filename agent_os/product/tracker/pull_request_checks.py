"""The CI checks of the pull request that closes an issue, as one verdict.

`issues.py move N review` is the one door an approved pull request goes through, so the gate is
here and not in the validator's prompt alone: a model that read `FAILURE` and approved anyway
(the first real worker of a host, 2026-10) cannot reach the human's "ready" page.
"""

import re
from dataclasses import dataclass

CLOSES_ISSUE_PATTERN = re.compile(r"(?im)^closes #(?P<issue>\d+)\b")

RED_CONCLUSIONS = frozenset(
    {"FAILURE", "TIMED_OUT", "CANCELLED", "STARTUP_FAILURE", "ACTION_REQUIRED", "STALE", "ERROR"}
)
GREEN_CONCLUSIONS = frozenset({"SUCCESS", "NEUTRAL", "SKIPPED"})


@dataclass(frozen=True)
class ChecksVerdict:
    pull_request: int
    red: tuple[str, ...]
    pending: tuple[str, ...]

    @property
    def is_green(self) -> bool:
        return not self.red and not self.pending

    def refusal(self) -> str:
        parts = []
        if self.red:
            parts.append("failing: " + ", ".join(self.red))
        if self.pending:
            parts.append("not finished: " + ", ".join(self.pending))
        return (
            f"pull request #{self.pull_request} is not ready, its CI checks are not all green "
            f"({'; '.join(parts)}). Request changes citing the check, or wait for it."
        )


def _check_name_and_outcome(entry: dict) -> tuple[str, str]:
    """A check run reports `status` + `conclusion`; a legacy commit status reports only `state`.
    The outcome is `PENDING` until something final is known."""
    name = entry.get("name") or entry.get("context") or "(unnamed check)"
    if "state" in entry and "conclusion" not in entry:
        state = (entry.get("state") or "").upper()
        return name, {"SUCCESS": "SUCCESS", "FAILURE": "FAILURE", "ERROR": "ERROR"}.get(
            state, "PENDING"
        )
    if (entry.get("status") or "").upper() != "COMPLETED":
        return name, "PENDING"
    return name, (entry.get("conclusion") or "PENDING").upper()


def verdict_for_rollup(pull_request: int, rollup: list[dict]) -> ChecksVerdict:
    red, pending = [], []
    for entry in rollup:
        name, outcome = _check_name_and_outcome(entry)
        if outcome in GREEN_CONCLUSIONS:
            continue
        (red if outcome in RED_CONCLUSIONS else pending).append(name)
    return ChecksVerdict(pull_request, tuple(red), tuple(pending))


def pull_request_closing(issue: int, open_pull_requests: list[dict]) -> dict | None:
    for pull_request in open_pull_requests:
        match = CLOSES_ISSUE_PATTERN.search(pull_request.get("body") or "")
        if match and int(match["issue"]) == issue:
            return pull_request
    return None


def refusal_for_issue(issue: int, open_pull_requests: list[dict]) -> str | None:
    """Why `issue` may not be moved to review, or None. An issue without an open pull request is
    not gated here: a human moving a card by hand is not an approval."""
    pull_request = pull_request_closing(issue, open_pull_requests)
    if pull_request is None:
        return None
    verdict = verdict_for_rollup(
        int(pull_request["number"]), pull_request.get("statusCheckRollup") or []
    )
    return None if verdict.is_green else verdict.refusal()
