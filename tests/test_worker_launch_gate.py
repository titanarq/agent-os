"""A worker class's launch reads its own declarations: `fallback:` and `escalate:` (#95).

Two things a worker class could declare and the launch never read. `fallback:` parsed on any class
but only the one-shot roles' drivers consulted it, so it silenced the guard's
`quota_exhausted_no_fallback` page for a run nothing could reroute; and nothing could say "default
model X, escalate to Y on the same backend once a stage was cut or failed".

Pure filesystem and subprocess: the driver tests put a fake backend first on PATH and never reach a
real one. This file must not request the `engine` or `db_sandbox` fixture.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import sys
from datetime import UTC, datetime, timedelta

import pytest
import yaml
from conftest import EXAMPLE_CONFIG
from pydantic import ValidationError
from test_worker_task import (
    _resume,
    _staged_body,
    _staged_environment,
    _start,
    _stop,
)

from agent_os import lib as agent_lib
from agent_os.lib import (
    ClassEscalation,
    RoleFallback,
    TaskClass,
    load_task_classes,
    quota_verdict_file,
    worker_launch,
)

VERDICT_TTL_SECONDS = 60 * 60


def _worker_class(**overrides) -> TaskClass:
    fields: dict = {
        "backend": "claude",
        "model": "claude-sonnet-5-5",
        "max_context": 400000,
        "max_cost_usd": 5.0,
        "max_total_tokens": 80000000,
        "commit_warn_turns": 30,
        "commit_cut_turns": 50,
    }
    fields.update(overrides)
    return TaskClass(**fields)


def _escalation(**overrides) -> ClassEscalation:
    fields: dict = {"model": "claude-opus-5-5"}
    fields.update(overrides)
    return ClassEscalation(**fields)


def _qwen_fallback() -> RoleFallback:
    return RoleFallback(backend="qwen", model="qwen3.8-max", ceilings=["max_total_tokens"])


def _write_verdict(cache_dir, status, *, age=timedelta(), backend="claude"):
    path = quota_verdict_file(backend, cache_dir=cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"last_quota_status": status}))
    observed_at = datetime.now(UTC) - age
    os.utime(path, (observed_at.timestamp(), observed_at.timestamp()))


def _config_with(tmp_path, **class_fields) -> pathlib.Path:
    """The example config plus one Claude worker class, `dev-claude`, carrying `class_fields`."""
    data = yaml.safe_load(EXAMPLE_CONFIG.read_text())
    data["classes"]["dev-claude"] = {
        "backend": "claude",
        "model": "claude-sonnet-5-5",
        "max_context": 400000,
        "max_cost_usd": 5.0,
        "max_total_tokens": 80000000,
        "commit_warn_turns": 30,
        "commit_cut_turns": 50,
        **class_fields,
    }
    path = tmp_path / "agents.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
    return path


ESCALATE = {"model": "claude-opus-5-5", "after": ["commit_cut", "stage_failed"]}
FALLBACK = {"backend": "qwen", "model": "qwen3.8-max", "ceilings": ["max_total_tokens"]}


# ---- the declaration -----------------------------------------------------------------------


def test_a_class_declares_no_escalation_unless_it_says_so():
    assert all(task_class.escalate is None for task_class in load_task_classes().values())
    assert _escalation().after == ["commit_cut", "stage_failed"]


def test_an_escalation_to_the_model_the_class_already_runs_is_refused():
    with pytest.raises(ValidationError, match="already the class's own model"):
        _worker_class(escalate=_escalation(model="claude-sonnet-5-5"))


def test_only_a_worker_class_may_escalate():
    with pytest.raises(ValidationError, match="worker"):
        _worker_class(role="validator", escalate=_escalation())


@pytest.mark.parametrize(
    "after", [[], ["commit_cut", "commit_cut"], ["quota"]], ids=["empty", "repeated", "unknown"]
)
def test_an_escalation_trigger_list_has_to_name_real_triggers_once_each(after):
    with pytest.raises(ValidationError):
        _escalation(after=after)


def test_a_worker_fallback_is_honoured_by_the_launch_so_the_guard_page_may_stay_quiet():
    # The one predicate behind the guard's `quota_exhausted_no_fallback` page. A worker class's
    # `fallback:` is read by the worker driver's launch (`worker-launch`), so it IS a way round.
    assert _worker_class(fallback=_qwen_fallback()).allows_backend_fallback is True
    assert _worker_class().allows_backend_fallback is False
    # Escalation stays on the same backend: it is no way round an exhausted quota.
    assert _worker_class(escalate=_escalation()).allows_backend_fallback is False


# ---- the decision --------------------------------------------------------------------------


def _plan(task_class, verdict="allowed", age=60.0, after=None, driver_backend="claude"):
    return worker_launch(
        task_class,
        driver_backend,
        after,
        verdict,
        age,
        verdict_ttl_seconds=VERDICT_TTL_SECONDS,
    )


def test_an_exhausted_fresh_verdict_substitutes_the_declared_fallback_and_its_ceilings():
    plan = _plan(_worker_class(fallback=_qwen_fallback()), "exhausted")
    assert (plan.backend, plan.model, plan.substituted) == ("qwen", "qwen3.8-max", True)
    assert plan.ceilings == ("max_total_tokens",)
    assert "fallback" in plan.reason


def test_the_substitution_wins_over_an_escalation_because_the_backend_is_what_is_out():
    task_class = _worker_class(fallback=_qwen_fallback(), escalate=_escalation())
    plan = _plan(task_class, "exhausted", after="commit_cut")
    assert (plan.backend, plan.substituted, plan.escalated) == ("qwen", True, False)


@pytest.mark.parametrize("after", ["commit_cut", "stage_failed"])
def test_a_declared_trigger_runs_the_stronger_model_on_the_same_backend(after):
    plan = _plan(_worker_class(escalate=_escalation()), after=after)
    assert (plan.backend, plan.model) == ("claude", "claude-opus-5-5")
    assert (plan.substituted, plan.escalated) == (False, True)
    assert "claude-sonnet-5-5" in plan.reason and after in plan.reason


@pytest.mark.parametrize("after", [None, "", "stage_failed"])
def test_no_trigger_or_an_undeclared_one_keeps_the_classs_own_model(after):
    task_class = _worker_class(escalate=_escalation(after=["commit_cut"]))
    plan = _plan(task_class, after=after)
    assert (plan.model, plan.escalated) == ("claude-sonnet-5-5", False)


def test_a_stale_exhausted_verdict_reads_as_unknown_and_launches_the_own_backend():
    plan = _plan(_worker_class(fallback=_qwen_fallback()), "exhausted", age=3 * 3600.0)
    assert (plan.backend, plan.substituted) == ("claude", False)


def test_a_class_on_another_backend_than_the_driver_is_left_to_the_drivers_own_model():
    plan = _plan(_worker_class(escalate=_escalation()), after="commit_cut", driver_backend="qwen")
    assert (plan.backend, plan.model, plan.substituted, plan.escalated) == (
        "qwen",
        "",
        False,
        False,
    )


def test_the_worker_launch_cli_prints_the_six_fields_the_driver_reads(
    tmp_path, monkeypatch, capsys
):
    config = _config_with(tmp_path, escalate=ESCALATE, fallback=FALLBACK)
    monkeypatch.setattr(agent_lib, "DEFAULT_AGENTS_CONFIG", config)
    _write_verdict(tmp_path, "allowed")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "agent_lib.py",
            "worker-launch",
            "dev-claude",
            "--backend",
            "claude",
            "--after",
            "commit_cut",
            "--cache-dir",
            str(tmp_path),
        ],
    )
    with pytest.raises(SystemExit) as exited:
        agent_lib.main()
    assert exited.value.code == 0
    fields = capsys.readouterr().out.rstrip("\n").split("\t")
    assert fields[:4] == ["claude", "claude-opus-5-5", "no", "yes"]
    assert len(fields) == 6


# ---- the driver ----------------------------------------------------------------------------


def _claude_worker_run(tmp_path, *, state=None, verdict=None, **class_fields):
    config = _config_with(tmp_path, **class_fields)
    environment, cache, _worktree, tmp = _staged_environment(
        tmp_path,
        stage_titles=("Write the failing test", "Make it pass"),
        mode="hang",
        subjects=("stage 1/2: Write the failing test",),
        config_path=config,
    )
    environment["GH_STUB_BODY"] = _staged_body("Write the failing test", "Make it pass").replace(
        "complex-qwen", "dev-claude"
    )
    environment["FAKE_BACKEND_ARGV"] = str(tmp / "argv.txt")
    if state is not None:
        (cache / "worker_claude.state").write_text(state + "\n")
        (cache / "worker_claude.issue").write_text("347\n")
        (cache / "worker_claude.brief.md").write_text("brief\n")
    if verdict is not None:
        _write_verdict(cache, verdict)
    return environment, cache, tmp


def _launched_model(tmp):
    argv = (tmp / "argv.txt").read_text()
    return re.search(r"--model (\S+)", argv).group(1)


def test_a_fresh_start_runs_the_classs_own_model_not_the_first_class_on_the_backend(tmp_path):
    environment, _cache, tmp = _claude_worker_run(tmp_path, escalate=ESCALATE)
    try:
        result = _start(environment, "347")
        assert result.returncode == 0, result.stdout + result.stderr
        assert _launched_model(tmp) == "claude-sonnet-5-5"
        assert "escalat" not in result.stdout.lower()
    finally:
        _stop(environment)


@pytest.mark.parametrize(
    "state",
    ["CUT_BY_GUARD reason=stall", "CUT_BY_GUARD reason=no_stage_commit"],
    ids=["commit_cut", "stage_failed"],
)
def test_the_stage_after_a_cut_or_failed_one_runs_the_stronger_model_and_says_so(tmp_path, state):
    environment, _cache, tmp = _claude_worker_run(tmp_path, state=state, escalate=ESCALATE)
    try:
        result = _resume(environment)
        assert result.returncode == 0, result.stdout + result.stderr
        assert _launched_model(tmp) == "claude-opus-5-5"
        assert "ESCALATED" in result.stdout and "claude-sonnet-5-5" in result.stdout
    finally:
        _stop(environment)


def test_an_escalation_that_does_not_list_the_trigger_leaves_the_model_alone(tmp_path):
    environment, _cache, tmp = _claude_worker_run(
        tmp_path,
        state="CUT_BY_GUARD reason=stall",
        escalate={"model": "claude-opus-5-5", "after": ["stage_failed"]},
    )
    try:
        assert _resume(environment).returncode == 0
        assert _launched_model(tmp) == "claude-sonnet-5-5"
    finally:
        _stop(environment)


def test_an_operator_pinned_model_beats_the_class_and_its_escalation(tmp_path):
    environment, _cache, tmp = _claude_worker_run(
        tmp_path, state="CUT_BY_GUARD reason=stall", escalate=ESCALATE
    )
    environment["WORKER_MODEL"] = "claude-haiku-5"
    try:
        assert _resume(environment).returncode == 0
        assert _launched_model(tmp) == "claude-haiku-5"
    finally:
        _stop(environment)


def test_start_refuses_a_class_whose_backend_is_out_and_names_where_it_goes(tmp_path):
    # A worker runs in a per-backend worktree with per-backend state, events and parser, so the
    # launch cannot swap the CLI under it: it refuses BEFORE any side effect and hands the
    # redispatch to the planner, exactly as `qwen_fallback_eligible` does.
    environment, cache, tmp = _claude_worker_run(tmp_path, verdict="exhausted", fallback=FALLBACK)
    result = _start(environment, "347")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "qwen" in result.stdout and "qwen3.8-max" in result.stdout
    assert "exhausted" in result.stdout
    assert not (tmp / "argv.txt").exists(), "a backend was launched"
    assert not (cache / "worker_claude.state").exists()
    assert not (cache / "worker_claude.issue").exists()


def test_start_launches_the_own_backend_when_the_class_declares_no_fallback(tmp_path):
    environment, _cache, tmp = _claude_worker_run(tmp_path, verdict="exhausted")
    try:
        result = _start(environment, "347")
        assert result.returncode == 0, result.stdout + result.stderr
        assert _launched_model(tmp) == "claude-sonnet-5-5"
    finally:
        _stop(environment)


def test_resume_refuses_an_exhausted_backend_with_a_fallback_too(tmp_path):
    environment, _cache, tmp = _claude_worker_run(
        tmp_path, state="CUT_BY_GUARD reason=quota", verdict="exhausted", fallback=FALLBACK
    )
    result = _resume(environment)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "qwen" in result.stdout
    assert not (tmp / "argv.txt").exists()
