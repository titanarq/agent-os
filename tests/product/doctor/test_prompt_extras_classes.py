"""`doctor.check_prompt_extras_classes`: a `prompt_extras` file naming a class `classes:` lacks."""

from __future__ import annotations

from agent_os import doctor
from agent_os.lib import ProjectConfig


def _project(**overrides) -> ProjectConfig:
    return ProjectConfig(repo="owner/name", tracking_epic=1, board_number=1, **overrides)


def _worker_class(**overrides):
    from agent_os.lib import TaskClass

    fields = {
        "backend": "claude",
        "model": "claude-sonnet-5-5",
        "max_context": 1,
        "max_cost_usd": 1.0,
        "max_total_tokens": 1,
        "commit_warn_turns": 1,
        "commit_cut_turns": 2,
    }
    fields.update(overrides)
    return TaskClass(**fields)


def test_check_prompt_extras_classes_warns_on_a_class_config_does_not_have(tmp_path):
    (tmp_path / "refiner.md").write_text("Use `complex-claude` for hard work.\n")
    project = _project(prompt_extras={"refiner": "refiner.md"})
    classes = {"complex-qwen": _worker_class(backend="qwen")}
    check = doctor.check_prompt_extras_classes(project, classes, tmp_path)
    assert check.ok and check.warning
    assert "complex-claude" in check.detail and "refiner" in check.detail
    assert check.line().startswith("[warn]")


def test_check_prompt_extras_classes_passes_when_every_named_class_exists(tmp_path):
    (tmp_path / "refiner.md").write_text(
        "Use `complex-qwen`; the `auto-ready` label is not a class.\n"
    )
    project = _project(prompt_extras={"refiner": "refiner.md"})
    classes = {"complex-qwen": _worker_class(backend="qwen")}
    check = doctor.check_prompt_extras_classes(project, classes, tmp_path)
    assert check.ok and not check.warning


def test_check_prompt_extras_classes_reads_budget_lines(tmp_path):
    (tmp_path / "planner.md").write_text("<!-- budget: gone-class -->\n")
    project = _project(prompt_extras={"planner": "planner.md"})
    check = doctor.check_prompt_extras_classes(project, {"complex-qwen": _worker_class()}, tmp_path)
    assert check.warning and "gone-class" in check.detail


def test_check_prompt_extras_classes_passes_with_no_extras(tmp_path):
    check = doctor.check_prompt_extras_classes(_project(), {}, tmp_path)
    assert check.ok and not check.warning
