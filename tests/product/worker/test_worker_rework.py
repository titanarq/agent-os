"""`resume --issue <N> --rework`: a run whose every stage is committed, sent back by its review.

The driver is the real one with a fake backend first in PATH; `gh` is a wrapper that answers the
pull-request list and keeps the issue body a PATCH wrote, and hands every other call to the staged
stub the other driver tests use. No backend is ever launched for real.
"""

from __future__ import annotations

import json
import os
import subprocess

from test_worker_task import DRIVER, ROOT, _staged_environment, _stop, _subjects

STAGES = ("Write the failing test", "Make it pass")
FINISHED = ("stage 1/2: Write the failing test", "stage 2/2: Make it pass")
REWORK_TITLE = "Address the changes requested on PR #42"

GH_WRAPPER = """#!/usr/bin/env python3
import json, os, pathlib, subprocess, sys

args = sys.argv[1:]
state = pathlib.Path(os.environ["REWORK_STATE_DIR"])
body_file = state / "body.md"
if args[:2] == ["pr", "list"]:
    print(pathlib.Path(os.environ["REWORK_PULL_REQUESTS"]).read_text())
    sys.exit(0)
if args[:1] == ["api"] and "PATCH" in args and any(a.startswith("body=") for a in args):
    body_file.write_text(next(a for a in args if a.startswith("body="))[len("body="):])
    print(json.dumps({"number": 347}))
    sys.exit(0)
if args[:2] == ["issue", "view"] and "--json" in args and args[args.index("--json") + 1] == "body":
    print(body_file.read_text() if body_file.is_file() else os.environ["GH_STUB_BODY"])
    sys.exit(0)
sys.exit(subprocess.run([os.environ["STAGED_GH"], *args]).returncode)
"""


def _rework_environment(tmp_path, reviews, *, subjects=FINISHED):
    environment, cache, worktree, tmp = _staged_environment(
        tmp_path, stage_titles=STAGES, mode="hang", subjects=subjects
    )
    state_dir = tmp_path / "rework_state"
    state_dir.mkdir()
    wrapper_dir = tmp_path / "gh_wrapper"
    wrapper_dir.mkdir()
    (wrapper_dir / "gh").write_text(GH_WRAPPER)
    (wrapper_dir / "gh").chmod(0o755)
    pull_requests = tmp_path / "pull_requests.json"
    pull_requests.write_text(json.dumps([{"number": 42, "reviews": reviews}]))
    staged_gh = environment["PATH"].split(os.pathsep)[0] + "/gh"
    environment = {
        **environment,
        "PATH": f"{wrapper_dir}{os.pathsep}{environment['PATH']}",
        "STAGED_GH": staged_gh,
        "REWORK_STATE_DIR": str(state_dir),
        "REWORK_PULL_REQUESTS": str(pull_requests),
    }
    (cache / "worker_claude.issue").write_text("347\n")
    (cache / "worker_claude.brief.md").write_text("the brief\n")
    (cache / "worker_claude.state").write_text("DONE\n")
    return environment, cache, worktree, tmp, state_dir


def _resume(environment, *arguments):
    return subprocess.run(
        ["bash", str(DRIVER), "claude", "resume", "--issue", "347", *arguments],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


CHANGES = [{"state": "CHANGES_REQUESTED", "body": "Rename `price` to `unit_price` everywhere."}]


def test_a_plain_resume_of_a_finished_run_still_has_nothing_to_launch(tmp_path):
    """The contrast: without `--rework` nothing about the review is read, so nothing is owed."""
    environment, _cache, _worktree, _tmp, state_dir = _rework_environment(tmp_path, CHANGES)
    result = _resume(environment)
    assert "nothing to launch" in result.stdout, result.stdout + result.stderr
    assert not (state_dir / "body.md").exists()


def test_rework_adds_the_stage_and_launches_it_with_the_review_as_context(tmp_path):
    environment, cache, _worktree, tmp, state_dir = _rework_environment(tmp_path, CHANGES)
    try:
        result = _resume(environment, "--rework")
        assert result.returncode == 0, result.stdout + result.stderr
        assert f"rework stage: {REWORK_TITLE}" in result.stdout
        assert f"- [ ] {REWORK_TITLE}" in (state_dir / "body.md").read_text()
        assert (cache / "worker_claude.state").read_text().startswith("RESUMED")
        prompt = (tmp / "prompts.txt").read_text()
        assert f"Your only goal in this process: stage 3/3: {REWORK_TITLE}" in prompt
        assert "Rename `price` to `unit_price` everywhere." in prompt
    finally:
        _stop(environment)


def test_the_callers_own_context_follows_the_review(tmp_path):
    environment, _cache, _worktree, tmp, _state_dir = _rework_environment(tmp_path, CHANGES)
    try:
        result = _resume(environment, "--rework", "--context", "and keep the API stable")
        assert result.returncode == 0, result.stdout + result.stderr
        prompt = (tmp / "prompts.txt").read_text()
        assert prompt.index("Rename `price`") < prompt.index("and keep the API stable")
    finally:
        _stop(environment)


def test_a_second_rework_before_the_stage_is_committed_adds_no_second_stage(tmp_path):
    environment, _cache, _worktree, _tmp, state_dir = _rework_environment(tmp_path, CHANGES)
    try:
        assert _resume(environment, "--rework").returncode == 0
        _stop(environment)
        again = _resume(environment, "--rework")
        assert again.returncode == 0, again.stdout + again.stderr
        assert "(already planned)" in again.stdout
        assert (state_dir / "body.md").read_text().count(REWORK_TITLE) == 1
    finally:
        _stop(environment)


def test_rework_is_refused_when_the_newest_review_approves(tmp_path):
    reviews = [*CHANGES, {"state": "APPROVED", "body": "lgtm"}]
    environment, cache, worktree, _tmp, state_dir = _rework_environment(tmp_path, reviews)
    subjects_before = _subjects(worktree)
    result = _resume(environment, "--rework")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "rework refused" in result.stdout and "APPROVED" in result.stdout
    assert not (state_dir / "body.md").exists()
    assert (cache / "worker_claude.state").read_text().strip() == "DONE"
    assert not (cache / "worker_claude.pid").exists()
    assert _subjects(worktree) == subjects_before


def test_rework_is_refused_when_the_branch_has_no_open_pull_request(tmp_path):
    environment, _cache, _worktree, _tmp, state_dir = _rework_environment(tmp_path, [])
    environment["REWORK_PULL_REQUESTS"] = str(tmp_path / "none.json")
    (tmp_path / "none.json").write_text("[]")
    result = _resume(environment, "--rework")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "no open pull request" in result.stdout
    assert not (state_dir / "body.md").exists()
