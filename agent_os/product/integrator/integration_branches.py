"""The one definition of an integration branch.

The integrator opens an integration pull request (head `integration/<stamp>`, no `Closes #N`,
never merged, closed when its round ends). It is not work, so every reader that lists open pull
requests to act on them skips it through `is_integration_branch`.
"""

from __future__ import annotations

INTEGRATION_BRANCH_PREFIX = "integration/"


def is_integration_branch(head_branch_name: str | None) -> bool:
    return (head_branch_name or "").startswith(INTEGRATION_BRANCH_PREFIX)


def without_integration_pull_requests(pull_requests: list[dict]) -> list[dict]:
    """The rows whose `headRefName` is not an integration branch."""
    return [row for row in pull_requests if not is_integration_branch(row.get("headRefName"))]
