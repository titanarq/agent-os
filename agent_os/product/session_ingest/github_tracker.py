"""The rework tickets on GitHub: found by their `<!-- key: -->` line, opened through the tracker CLI's
own wrappers, so the rate-limit handling and the repository resolution are `agent_os.issues`'."""

from __future__ import annotations

from agent_os.issues import create_issue, find_by_key, repo_name
from agent_os.product.session_ingest.rework_ticket import rework_key


class GitHubReworkTracker:
    def __init__(self) -> None:
        self._repo: str | None = None

    @property
    def repo(self) -> str:
        """Resolved at the first call that needs it, so that a run with nothing rejected never asks."""
        if self._repo is None:
            self._repo = repo_name()
        return self._repo

    def find(self, session_id: str, node_id: str) -> int | None:
        return self.find_by_key(rework_key(session_id, node_id))

    def find_by_key(self, key: str) -> int | None:
        return find_by_key(self.repo, key)

    def open(self, title: str, body: str, labels: list[str]) -> int:
        return int(create_issue(self.repo, title, body, labels)["number"])
