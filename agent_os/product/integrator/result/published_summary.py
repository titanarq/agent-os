"""The suite summary index the integration head's CI published as an artifact: `result` fetches it
itself when `--summary-index` is not given, so a red group can still point at the member to evict."""

from __future__ import annotations

import json
import pathlib
import tempfile

from agent_os.product.integrator.facts import RunCommand

SUMMARY_ARTIFACT_NAME = "agent-os-suite-summary"
SUMMARY_FILE_NAME = "suite.summary.json"


def fetch_published_summary(
    run: RunCommand,
    pull_request: int,
    repo_flags: list[str],
    destination: pathlib.Path | None = None,
) -> pathlib.Path | None:
    """The downloaded `suite.summary.json` of the newest run of the PR's current head, or None."""
    viewed = run(["gh", "pr", "view", str(pull_request), *repo_flags, "--json", "headRefOid"])
    if viewed.returncode != 0:
        return None
    head_sha = json.loads(viewed.stdout).get("headRefOid")
    listed = run(
        [
            "gh",
            "run",
            "list",
            *repo_flags,
            "--commit",
            head_sha,
            "--json",
            "databaseId",
            "--limit",
            "20",
        ]
    )
    if not head_sha or listed.returncode != 0:
        return None
    target = destination or pathlib.Path(tempfile.mkdtemp(prefix="agent-os-summary-"))
    for candidate in json.loads(listed.stdout or "[]"):
        downloaded = run(
            [
                "gh", "run", "download", str(candidate["databaseId"]), *repo_flags,
                "--name", SUMMARY_ARTIFACT_NAME, "--dir", str(target),
            ]
        )  # fmt: skip
        if downloaded.returncode == 0 and (target / SUMMARY_FILE_NAME).is_file():
            return target / SUMMARY_FILE_NAME
    return None
