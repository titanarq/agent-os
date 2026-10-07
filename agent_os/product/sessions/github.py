"""What a session needs from GitHub: the issue it opens, the owner's replies, a pull request's files.

Everything goes through `agent_os.issues`' `gh` wrappers, so the rate-limit handling and the
repository resolution are the tracker CLI's own.
"""

from __future__ import annotations

import urllib.parse

from agent_os import lib
from agent_os.issues import create_issue, gh_json, gh_json_dict, gh_text
from agent_os.product.sessions.what_guard import BASE, HEAD, FileChange, FileReader

COMMENTS_PER_PAGE = 100


def open_session_issue(repo: str, title: str, body: str, labels: list[str]) -> int:
    return int(create_issue(repo, title, body, labels)["number"])


def issue_body(repo: str, number: int) -> str:
    return gh_json_dict("api", f"repos/{repo}/issues/{number}").get("body") or ""


def owner_comments(repo: str, number: int, project: lib.ProjectConfig) -> list[str]:
    """The comments of the owner (`project.human_login`), oldest first: an agent's own comment on
    the session is never an answer."""
    rows = gh_json("api", f"repos/{repo}/issues/{number}/comments?per_page={COMMENTS_PER_PAGE}")
    owner_rows = [
        row
        for row in rows or []
        if lib.is_human_comment((row.get("user") or {}).get("login", ""), project)
    ]
    owner_rows.sort(key=lambda row: row.get("created_at", ""))
    return [row.get("body") or "" for row in owner_rows]


def pull_request_changes(repo: str, number: int) -> list[FileChange]:
    rows = gh_json("api", f"repos/{repo}/pulls/{number}/files?per_page=100") or []
    return [FileChange(row["filename"], row.get("previous_filename")) for row in rows]


def pull_request_file_reader(repo: str, number: int) -> FileReader:
    """Reads a file as the base and as the head of the pull request. A file absent on a side is
    None; any other failure of `gh` stops the run, because an unreadable file must not read as
    clean."""
    pull = gh_json_dict("api", f"repos/{repo}/pulls/{number}")
    revision = {BASE: pull["base"]["sha"], HEAD: pull["head"]["sha"]}

    def read_file(side: str, path: str) -> str | None:
        address = f"repos/{repo}/contents/{urllib.parse.quote(path)}?ref={revision[side]}"
        try:
            return gh_text("api", "-H", "Accept: application/vnd.github.raw", address)
        except SystemExit as failure:
            if "404" in str(failure) or "Not Found" in str(failure):
                return None
            raise

    return read_file


def pull_request_body(repo: str, number: int) -> str:
    return gh_json_dict("api", f"repos/{repo}/pulls/{number}").get("body") or ""
