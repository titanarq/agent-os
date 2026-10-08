"""The Project v2 boards a repository shows, read through the caller's `gh` JSON reader."""

from __future__ import annotations

from collections.abc import Callable

# The Projects linked to one repository, each with its owner's login: `repository.projectsV2`
# answers exactly "which boards does this repo show", which `gh project list --owner` cannot.
LINKED_PROJECTS_QUERY = """
query($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    projectsV2(first: 100) {
      nodes { number owner { ... on Organization { login } ... on User { login } } }
    }
  }
}
"""


def linked_boards(repo: str, read_json: Callable) -> set[tuple[int, str]]:
    """`(number, lowercased owner login)` for every Project v2 linked to `repo`."""
    owner, name = repo.split("/", 1)
    response = read_json(
        "api",
        "graphql",
        "-f",
        f"query={LINKED_PROJECTS_QUERY}",
        "-F",
        f"owner={owner}",
        "-F",
        f"name={name}",
    )
    repository = ((response or {}).get("data") or {}).get("repository") or {}
    nodes = (repository.get("projectsV2") or {}).get("nodes") or []
    return {
        (node["number"], ((node.get("owner") or {}).get("login") or "").lower())
        for node in nodes
        if node and "number" in node
    }
