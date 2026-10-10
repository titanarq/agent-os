"""Which workflows of a host would report a check on a pull request that touches only host files.

The control plane counts zero checks on a PR's head SHA as merge condition 1 not met
(agent-os#50), and the installed `ci-agent-os.yml` is path-filtered to `agent_os/**`; the doctor
reads the workflows back with this (`docs/adoption/substrate.md` step 21).
"""

from __future__ import annotations

import pathlib

import yaml

PATH_FILTER_KEYS = ("paths", "paths-ignore")


def reports_on_every_pull_request(workflow: object) -> bool:
    """Whether a parsed workflow's `on:` fires on `pull_request` with no `paths`/`paths-ignore`
    filter. PyYAML reads the bare key `on` as the boolean True, so both spellings are looked up.
    A heuristic: it does not read job-level `if:` conditions or branch filters."""
    if not isinstance(workflow, dict):
        return False
    triggers = workflow.get("on", workflow.get(True))
    if triggers == "pull_request":
        return True
    if isinstance(triggers, list):
        return "pull_request" in triggers
    if isinstance(triggers, dict) and "pull_request" in triggers:
        pull_request = triggers["pull_request"] or {}
        return isinstance(pull_request, dict) and not any(
            key in pull_request for key in PATH_FILTER_KEYS
        )
    return False


def unfiltered_pull_request_workflows(workflows_dir: pathlib.Path) -> list[str]:
    """File names under `workflows_dir` whose `on:` fires on `pull_request` with no path filter,
    skipping a file that cannot be read or parsed."""
    candidates = sorted([*workflows_dir.glob("*.yml"), *workflows_dir.glob("*.yaml")])
    unfiltered = []
    for path in candidates:
        try:
            workflow = yaml.safe_load(path.read_text())
        except (OSError, yaml.YAMLError):
            continue
        if reports_on_every_pull_request(workflow):
            unfiltered.append(path.name)
    return unfiltered
