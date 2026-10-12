"""What keeps one candidate out of every group, judged on that pull request alone: it lands the way
it does today. Step 2 of the ADR, the rules that need no other pull request."""

from __future__ import annotations

import fnmatch
import pathlib
from collections.abc import Iterable

from agent_os.product.integrator.facts import PullRequestFacts
from agent_os.product.test_selection.manifest_changes import manifest_files_changed
from agent_os.product.test_selection.plan import TestPlan

# What changes the environment every test runs in is proved alone. A pattern without a slash is
# matched against the file name in any folder.
BUILT_IN_SOLO_PATHS = (
    ".github/**",
    "Dockerfile*",
    "bootstrap.sh",
    "pyproject.toml",
    "requirements*.txt",
    "uv.lock",
    "poetry.lock",
    "Pipfile",
    "Pipfile.lock",
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "go.mod",
    "go.sum",
    "Cargo.toml",
    "Cargo.lock",
    "Gemfile",
    "Gemfile.lock",
)


def _matches(path: str, pattern: str) -> bool:
    if "/" not in pattern:
        return fnmatch.fnmatchcase(pathlib.PurePosixPath(path).name, pattern)
    return fnmatch.fnmatchcase(path, pattern)


def solo_path_of(paths: Iterable[str], host_solo_paths: Iterable[str]) -> tuple[str, str] | None:
    patterns = [*BUILT_IN_SOLO_PATHS, *host_solo_paths]
    for path in paths:
        for pattern in patterns:
            if _matches(path, pattern):
                return path, pattern
    return None


def reason_to_land_alone(
    facts: PullRequestFacts,
    plan: TestPlan,
    host_solo_paths: Iterable[str],
    manifest_path: str,
) -> str | None:
    solo = solo_path_of(facts.paths, host_solo_paths)
    if solo is not None:
        return f"{solo[0]} matches the solo path {solo[1]}"
    if manifest_path and manifest_files_changed(list(facts.paths), manifest_path):
        return "it changes the test manifest, which its own plan is computed from"
    if plan.mode == "full":
        return f"its own test plan is the whole suite ({plan.reason})"
    return None
