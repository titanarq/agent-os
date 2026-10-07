"""The mechanism's own CI judges the Node-Change trailer of a pull request's commits (#130)."""

from __future__ import annotations

from pathlib import Path

import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_the_ci_workflow_runs_the_trailer_check_on_pull_requests_over_their_own_range():
    workflow = yaml.safe_load((REPOSITORY_ROOT / ".github/workflows/ci.yml").read_text())
    steps = workflow["jobs"]["tests"]["steps"]
    trailer_steps = [step for step in steps if "tree trailers" in step.get("run", "")]
    assert len(trailer_steps) == 1
    step = trailer_steps[0]
    assert step["if"] == "github.event_name == 'pull_request'"
    assert "--base origin/${{ github.base_ref }}" in step["run"]
    assert "--root docs/tree" in step["run"]
