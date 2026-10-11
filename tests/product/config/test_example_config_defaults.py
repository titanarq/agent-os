"""What the shipped `config.example.yaml` and the install templates say by default: one backend,
Claude Code, Haiku for the puntal and mechanical tasks, Sonnet for every other
role, Opus only for the two Stage 2 roles (`docs/tree/dec-one-backend-claude-code-with-opus-at-the-top.md`,
agent-os#116; `docs/adr/2026-10-10-puntals-and-mechanical-tasks-default-to-haiku-5-5.md`)."""

from __future__ import annotations

from conftest import SHIPPED_EXAMPLE_CONFIG

from agent_os.cli import AGENT_OS_DIR
from agent_os.lib import AgentModels, backend_default_model, load_agents_config

SONNET = "claude-sonnet-5-5"
HAIKU = "claude-haiku-5-5"
CLASSES_ON_HAIKU = {"puntal", "mechanical-haiku"}


def shipped_config():
    return load_agents_config(SHIPPED_EXAMPLE_CONFIG)


def test_the_example_describes_exactly_one_backend_and_it_is_claude():
    assert list(shipped_config().project.backends) == ["claude"]


def test_every_class_of_the_example_runs_on_claude_and_none_has_a_fallback():
    classes = shipped_config().classes
    assert classes
    for name, task_class in classes.items():
        assert task_class.backend == "claude", name
        assert task_class.fallback is None, name


def test_the_puntal_and_mechanical_haiku_run_on_haiku_and_every_other_class_on_sonnet():
    classes = shipped_config().classes
    assert CLASSES_ON_HAIKU <= set(classes)
    for name, task_class in classes.items():
        assert task_class.model == (HAIKU if name in CLASSES_ON_HAIKU else SONNET), name


def test_mechanical_sonnet_still_exists_for_the_issues_that_name_it():
    classes = shipped_config().classes
    assert classes["mechanical-sonnet"].model == SONNET
    assert classes["mechanical-sonnet"].role == classes["mechanical-haiku"].role == "worker"


def test_a_worker_dispatched_with_no_class_still_gets_sonnet():
    assert backend_default_model("claude", SHIPPED_EXAMPLE_CONFIG) == SONNET


def test_the_example_names_no_action_of_a_host_in_action_models():
    assert shipped_config().puntal.action_models == {}


def test_the_refiner_and_the_task_writer_are_on_sonnet_too():
    config = shipped_config()
    assert config.classes["refiner"].model == SONNET
    assert config.project.agent_models.task_writer == "sonnet"


def test_the_custodian_and_the_consolidator_default_to_opus_and_every_other_role_to_sonnet():
    models = AgentModels()
    assert (models.custodian, models.consolidator) == ("opus", "opus")
    assert (models.control_plane, models.worker_runner, models.task_writer) == (
        "sonnet",
        "sonnet",
        "sonnet",
    )
    assert shipped_config().project.agent_models == models


def test_the_example_tree_budget_class_is_one_of_its_worker_classes():
    config = shipped_config()
    assert config.tree.ticket_budget_class in config.classes


def test_the_install_templates_name_no_qwen_class_or_backend():
    for path in sorted((AGENT_OS_DIR / "templates").rglob("*.*")):
        assert "qwen" not in path.read_text().lower(), path
