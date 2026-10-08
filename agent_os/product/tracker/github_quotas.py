"""Which of the `gh` login's API quotas are at zero right now."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime


def exhausted_quotas(run_gh: Callable[..., subprocess.CompletedProcess]) -> list[str] | None:
    """One line per quota of this `gh` login that is at zero right now -- `graphql: 0 of 5000
    left, resets at ...` -- or None when the quotas could not be read. `gh api rate_limit` is
    free: it counts against none of them.

    Every API has its own bucket: `core` (REST), `graphql`, `search`... The top-level `.rate`
    that `gh api rate_limit` prints first is `core` alone, so it can read `remaining: 5000` while
    `graphql` is at zero, and every GraphQL-backed `gh` subcommand answers "API rate limit already
    exceeded" (#70). Naming the empty bucket is what tells that apart from a transient refusal."""
    result = run_gh("api", "rate_limit", "--jq", ".resources")
    if result.returncode != 0:
        return None
    try:
        resources = json.loads(result.stdout)
    except ValueError:
        return None
    if not isinstance(resources, dict):
        return None
    lines = []
    for name, bucket in sorted(resources.items()):
        if not isinstance(bucket, dict) or bucket.get("remaining") != 0:
            continue
        reset = datetime.fromtimestamp(int(bucket.get("reset") or 0), UTC)
        lines.append(
            f"{name}: 0 of {bucket.get('limit')} left, resets at {reset:%Y-%m-%dT%H:%M:%SZ}"
        )
    return lines
