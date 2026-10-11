"""`agent-os-tests last-full-run`: the age of the clock, read from the repository's Actions artifacts.

An unreadable clock prints `unknown`, never fails: it means a full run, and a skipped one would
be the dangerous mistake."""

from __future__ import annotations

import json
import subprocess
import sys

from agent_os.product.test_selection.clock.full_run_clock import NEVER, UNKNOWN, parse_last_full_run

DEFAULT_MARKER_NAME = "agent-os-full-run"


def _artifacts_of_marker(repository: str, marker_name: str) -> list[dict]:
    completed = subprocess.run(
        ["gh", "api", f"repos/{repository}/actions/artifacts?name={marker_name}&per_page=1"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"gh exited {completed.returncode}: {completed.stderr.strip()}")
    payload = json.loads(completed.stdout)
    artifacts = payload["artifacts"]
    if not isinstance(artifacts, list):
        raise TypeError("`artifacts` is not a list")
    return artifacts


def read_last_full_run(repository: str, marker_name: str) -> str:
    try:
        artifacts = _artifacts_of_marker(repository, marker_name)
        # The newest comes first, and an expired one means every older one expired too.
        if not artifacts or artifacts[0].get("expired"):
            return NEVER
        created_at = artifacts[0]["created_at"]
        parse_last_full_run(created_at)
        return created_at
    except (OSError, RuntimeError, ValueError, TypeError, KeyError, AttributeError) as error:
        print(f"agent-os-tests: the last full run is unreadable: {error}", file=sys.stderr)
        return UNKNOWN
