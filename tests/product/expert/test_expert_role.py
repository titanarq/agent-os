"""The expert role (#118): a one-shot role in the validator/refiner pattern that populates the
product tree. These tests pin what the mechanism owes it -- a class of its own, a prompt that
carries its constraints, a driver that resolves it, an end the guard can announce -- and the
launch path against a stub backend. No network, no real backend, no tracker."""

from __future__ import annotations

import os
import pathlib
import subprocess

import pytest
import yaml
from conftest import SHIPPED_EXAMPLE_CONFIG
from test_agent_task import (  # the launch fixtures are shared, not copied
    DRIVER,
    NO_VERDICT_CACHE_DIR,
    ROOT,
    _host,
    _launch,
    _prompt,
    _record,
    launch_environment,  # noqa: F401
)

from agent_os import guard
from agent_os.lib import (
    PLACEHOLDER_RE,
    PROMPT_ROLES,
    PROMPTS_DIR,
    load_role_class,
    load_task_classes,
    prompt_substitutions,
    render_prompt,
    render_worker_classes,
)


def _expert_rules() -> str:
    values = prompt_substitutions()
    values["WORKTREE"] = "/a/worktree"
    return render_prompt("expert", values)


def _flattened(text: str) -> str:
    return " ".join(text.split())


def test_the_example_config_carries_one_expert_class_on_sonnet():
    _, expert_class = load_role_class("expert")
    assert expert_class.role == "expert"
    assert "sonnet" in expert_class.model
    assert expert_class.fallback is None


def test_the_expert_class_is_never_offered_to_a_task_as_a_budget():
    assert "expert" not in render_worker_classes(load_task_classes())


def test_the_expert_has_a_prompt_template_like_every_other_role():
    assert "expert" in PROMPT_ROLES
    assert (PROMPTS_DIR / "expert.md").is_file()


@pytest.mark.parametrize(
    "clause",
    [
        "Node-Change: usage",
        "Node-Change: rework",
        "default_answer",
        "scope",
        "challenge",
        "never touch a goal",
        "never ask the owner a question of how",
        "before the owner",
        "uc-start-a-new-product",
        "depends_on",
        "mechanism: pending",
    ],
)
def test_the_expert_prompt_carries_the_clause(clause):
    assert clause.lower() in _flattened(_expert_rules()).lower()


def test_the_expert_prompt_names_the_hosts_tree_root_from_config():
    assert "`product/`" in _expert_rules()


def test_the_expert_prompt_leaves_no_placeholder_unanswered():
    assert PLACEHOLDER_RE.findall(_expert_rules()) == []


def test_the_expert_is_a_one_shot_role_the_guard_watches_and_announces():
    assert "expert" in guard.ONE_SHOT_ROLES
    assert "expert_finished" in guard.EVENT_KINDS


def test_the_expert_has_its_own_class_name_in_the_example_config():
    classes = yaml.safe_load(SHIPPED_EXAMPLE_CONFIG.read_text())["classes"]
    assert [name for name, body in classes.items() if body.get("role") == "expert"] == ["expert"]


def test_the_driver_resolves_the_expert_on_a_dry_run():
    result = subprocess.run(
        ["bash", str(DRIVER), "expert", "7", "--dry-run"],
        cwd=ROOT,
        env={**os.environ, "WORKER_CACHE_DIR": NO_VERDICT_CACHE_DIR},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "role:      expert (class expert)" in result.stdout
    assert "Populate the product tree for issue #7" in result.stdout
    assert "--- rules ---" in result.stdout


def test_an_expert_launch_gets_a_worktree_of_its_own_and_runs_inside_it(
    launch_environment,  # noqa: F811
):
    result = _launch(launch_environment, "expert", "7")
    assert result.returncode == 0, result.stdout + result.stderr
    seen = _record(launch_environment)
    worktree = pathlib.Path(seen["WORKTREE"])
    assert worktree.parent == pathlib.Path(launch_environment["AGENT_CACHE_DIR"])
    assert seen["PWD"] == str(worktree), "the expert commits in its worktree, so it starts there"
    assert seen["WORKTREE_GIT"] == "yes"
    assert str(worktree) in _prompt(launch_environment)
    assert _host(launch_environment) != worktree


def test_an_expert_launch_with_no_worktree_refuses_and_launches_nothing(
    launch_environment,  # noqa: F811
):
    """The validator degrades to reading the diff; the expert WRITES, so it never starts in the main
    checkout (#135)."""
    del launch_environment["AGENT_WORKTREE_REF"]
    host = _host(launch_environment)
    subprocess.run(["git", "-C", str(host), "remote", "remove", "origin"], check=False)
    subprocess.run(
        ["git", "-C", str(host), "remote", "add", "origin", str(host / "no-such-origin")],
        check=True,
    )
    result = _launch(launch_environment, "expert", "7")
    assert result.returncode != 0, result.stdout + result.stderr
    assert "ERROR" in result.stdout, result.stdout
    assert not pathlib.Path(launch_environment["STUB_RECORD"]).exists(), "the backend ran"


def test_the_expert_prompt_defers_the_trees_language_to_the_hosts_agents_md():
    """A host's tree may be Spanish: the prompt names no language for what goes into the tree (#135)."""
    rules = _flattened(_expert_rules())
    assert "stays in English" not in rules
    assert "language rule" in rules
    assert "the host's own AGENTS.md" in rules
