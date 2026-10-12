"""Step 1 of the ADR: which pull requests may be considered. The answer is a reason to drop one, or
None; every fact the script could not read is a reason."""

from __future__ import annotations

from agent_os.product.integrator.facts import PullRequestFacts
from agent_os.product.tracker.pull_request_checks import is_integration_branch


def reason_not_a_candidate(facts: PullRequestFacts, default_branch: str) -> str | None:
    if facts.unreadable_reason:
        return f"a fact could not be read ({facts.unreadable_reason})"
    if not facts.is_open:
        return "not open"
    if is_integration_branch(facts.head_branch):
        return "it is an integration pull request"
    if facts.is_draft:
        return "a draft"
    if facts.base != default_branch:
        return f"targets {facts.base}, not the default branch {default_branch}"
    if facts.mergeable != "MERGEABLE":
        return f"not mergeable ({facts.mergeable or 'unknown'})"
    if not facts.checks_are_green:
        return f"checks are not all green ({facts.checks_problem})"
    if not facts.approved_on_head:
        return "no approval on its current head, or a change is requested"
    return None
