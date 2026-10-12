"""Step 3 of the ADR: the fast pre-flight on the integrated tree, no tests. It catches the sums no
single pull request shows (two files added to a folder at its limit) before any CI is spent."""

from __future__ import annotations

import pathlib
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from agent_os.product.integrator.facts import RunCommand

_REFORMAT_LINE = re.compile(r"^Would reformat: (?P<path>.+)$")
_CONCISE_FINDING = re.compile(r"^(?P<path>[^:\s]+):\d+:\d+:")


def preflight_commands(tree: pathlib.Path, base_sha: str) -> list[tuple[str, list[str]]]:
    """Each step with the command that runs it from inside `tree`."""
    python = sys.executable
    return [
        ("ruff check", [python, "-m", "ruff", "check", "--output-format", "concise", "."]),
        ("ruff format", [python, "-m", "ruff", "format", "--check", "."]),
        (
            "quality ratchet",
            [python, "-m", "agent_os.quality", "--base", base_sha, "--root", str(tree)],
        ),
        ("test manifest", [python, "-m", "agent_os.product.test_selection.cli", "check"]),
    ]


@dataclass(frozen=True)
class PreflightFailure:
    step: str
    output: str
    paths: tuple[str, ...]


def _paths_named_in(output: str) -> tuple[str, ...]:
    named: list[str] = []
    for line in output.splitlines():
        reformat = _REFORMAT_LINE.match(line)
        finding = _CONCISE_FINDING.match(line)
        if reformat:
            named.append(reformat["path"].strip())
        elif finding:
            named.append(finding["path"])
        elif ": " in line:
            named.append(line.split(": ", 1)[0].strip())
    return tuple(dict.fromkeys(named))


def run_preflight(
    run_in_tree: RunCommand, tree: pathlib.Path, base_sha: str
) -> PreflightFailure | None:
    """The first step that fails, with the paths it names; None when all four pass. A failing
    step stops the rest: one defect is enough to send the group back."""
    for step, command in preflight_commands(tree, base_sha):
        outcome = run_in_tree(command)
        if outcome.returncode != 0:
            output = (outcome.stdout + outcome.stderr).strip()
            return PreflightFailure(step, output, _paths_named_in(output))
    return None


def members_contributing(
    failure: PreflightFailure, paths_by_member: Mapping[int, Sequence[str]]
) -> tuple[int, ...]:
    """The members whose changed paths are, or sit under, a path the failure names. A folder
    over its limit names the folder, so every member that added to it is named."""

    def covers(named: str, changed: str) -> bool:
        return named in (".", changed) or changed.startswith(named.rstrip("/") + "/")

    return tuple(
        sorted(
            number
            for number, changed_paths in paths_by_member.items()
            if any(covers(named, changed) for named in failure.paths for changed in changed_paths)
        )
    )


def describe_failure(
    failure: PreflightFailure, paths_by_member: Mapping[int, Sequence[str]]
) -> str:
    members = members_contributing(failure, paths_by_member)
    contributors = " ".join(f"#{number}" for number in members) or "no single member"
    return (
        f"pre-flight failed at {failure.step}; paths: "
        f"{', '.join(failure.paths) or '(none named)'}; contributed by: {contributors}\n"
        f"{failure.output}"
    )
