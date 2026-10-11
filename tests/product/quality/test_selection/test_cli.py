import json
import stat

import pytest
from selection_support import (
    commit_all,
    make_repository,
    write_file,
)

from agent_os.product.test_selection import cli


def run(repository, capsys, *arguments):
    code = cli.main(["--root", str(repository), *arguments])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


@pytest.fixture
def repository(tmp_path):
    return make_repository(tmp_path)


def test_check_is_clean_defective_and_off(repository, capsys):
    assert run(repository, capsys, "check", "--manifest", "manifest.yaml")[0] == 0
    write_file(repository, "tests/test_stray.py")
    code, out, _ = run(repository, capsys, "check", "--manifest", "manifest.yaml")
    assert code == 1 and "tests/test_stray.py" in out
    code, out, _ = run(repository, capsys, "check")
    assert (code, out.strip()) == (0, "test selection is off")


def test_check_could_not_run_on_a_missing_manifest(repository, capsys):
    assert run(repository, capsys, "check", "--manifest", "ghost.yaml")[0] == 2


def test_plan_in_each_format(repository, capsys):
    write_file(repository, "bin/worker.sh", "changed\n")
    commit_all(repository)
    base = ["plan", "--base", "main", "--manifest", "manifest.yaml"]
    code, out, _ = run(repository, capsys, *base, "--format", "json")
    plan = json.loads(out)
    assert code == 0 and plan["mode"] == "selected" and plan["groups"] == ["worker"]
    assert set(plan) == {"mode", "reason", "groups", "tests", "unmapped_paths"}
    _, out, _ = run(repository, capsys, *base, "--format", "paths")
    assert "tests/test_worker.py" in out.splitlines()
    _, out, _ = run(repository, capsys, *base)
    assert out.startswith("mode: selected")


def test_plan_reads_the_manifest_change(repository, capsys):
    changed = (
        (repository / "manifest.yaml")
        .read_text()
        .replace("covers: [prompts/]", "covers: [prompts/, extra/]")
    )
    write_file(repository, "manifest.yaml", changed)
    commit_all(repository)
    _, out, _ = run(
        repository,
        capsys,
        "plan",
        "--base",
        "main",
        "--manifest",
        "manifest.yaml",
        "--format",
        "json",
    )
    assert json.loads(out)["groups"] == ["prompts"]


def test_plan_without_a_manifest_is_full_and_with_a_broken_one_is_exit_1_or_2(repository, capsys):
    _, out, _ = run(repository, capsys, "plan", "--base", "main")
    assert "test selection is off" in out
    write_file(repository, "bad.yaml", "nonsense: 1\n")
    assert run(repository, capsys, "plan", "--base", "main", "--manifest", "bad.yaml")[0] == 1
    assert (
        run(repository, capsys, "plan", "--base", "nowhere", "--manifest", "manifest.yaml")[0] == 2
    )


@pytest.fixture
def fake_runner(tmp_path):
    runner = tmp_path / "runner.sh"
    log = tmp_path / "runner.log"
    runner.write_text(f'#!/bin/sh\necho "$@" > {log}\nexit 7\n')
    runner.chmod(runner.stat().st_mode | stat.S_IEXEC)
    return runner, log


def test_run_execs_the_command_with_the_selected_paths_and_returns_its_code(
    repository, capsys, fake_runner
):
    runner, log = fake_runner
    write_file(repository, "bin/worker.sh", "changed\n")
    commit_all(repository)
    code, out, _ = run(
        repository,
        capsys,
        "run",
        "--base",
        "main",
        "--manifest",
        "manifest.yaml",
        "--command",
        f"{runner} -q",
    )
    assert code == 7 and out.startswith("mode: selected")
    assert log.read_text().split()[:2] == ["-q", "tests/test_worker.py"]


def test_run_full_and_a_failed_plan_run_the_command_alone(repository, capsys, fake_runner):
    runner, log = fake_runner
    run(
        repository,
        capsys,
        "run",
        "--base",
        "main",
        "--manifest",
        "manifest.yaml",
        "--command",
        str(runner),
        "--full",
    )
    assert log.read_text().strip() == ""
    code, _, err = run(
        repository,
        capsys,
        "run",
        "--base",
        "nowhere",
        "--manifest",
        "manifest.yaml",
        "--command",
        str(runner),
    )
    assert code == 7 and "running the whole suite" in err and log.read_text().strip() == ""
