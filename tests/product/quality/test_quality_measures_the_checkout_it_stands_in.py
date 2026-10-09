"""`agent-os-quality` judges the repository the shell stands in, not the host's main checkout.

The drivers export `AGENT_OS_HOST_ROOT`, the main checkout, to every process they launch, and the
ratchet used to take its root from it: run in a worker's worktree it measured `main`, found nothing
over a limit and exited 0 for a branch that CI would fail -- a false green, which is worse than
no check. The root is the git toplevel of the working directory; `--root` still names another one.
"""

import pathlib
import subprocess

import pytest

from agent_os.quality import cli

FILE_OVER_THE_LIMIT = "x\n" * 301


def git(repository: pathlib.Path, *arguments: str) -> None:
    subprocess.run(
        ["git", "-C", str(repository), "-c", "user.name=t", "-c", "user.email=t@t", *arguments],
        check=True,
        capture_output=True,
    )


@pytest.fixture
def main_checkout_and_a_worktree_over_the_limit(tmp_path):
    main_checkout = tmp_path / "main_checkout"
    main_checkout.mkdir()
    git(main_checkout, "init", "-q", "-b", "main")
    (main_checkout / "small.py").write_text("x\n")
    git(main_checkout, "add", "-A")
    git(main_checkout, "commit", "-q", "-m", "base")
    worktree = tmp_path / "worktree"
    git(main_checkout, "worktree", "add", "-q", "-b", "feature", str(worktree))
    (worktree / "grown.py").write_text(FILE_OVER_THE_LIMIT)
    git(worktree, "add", "-A")
    git(worktree, "commit", "-q", "-m", "a file over the limit")
    return main_checkout, worktree


def test_a_worktree_is_measured_when_the_drivers_name_the_main_checkout_as_host_root(
    main_checkout_and_a_worktree_over_the_limit, monkeypatch, capsys
):
    main_checkout, worktree = main_checkout_and_a_worktree_over_the_limit
    monkeypatch.setenv("AGENT_OS_HOST_ROOT", str(main_checkout))
    monkeypatch.chdir(worktree)

    assert cli.main(["--base", "main"]) == 1
    assert capsys.readouterr().out.startswith("grown.py: new, 301 lines")


def test_a_subdirectory_of_the_worktree_measures_the_whole_repository(
    main_checkout_and_a_worktree_over_the_limit, monkeypatch
):
    _main_checkout, worktree = main_checkout_and_a_worktree_over_the_limit
    (worktree / "package").mkdir()
    monkeypatch.chdir(worktree / "package")

    assert cli.main(["--base", "main"]) == 1


def test_a_root_given_on_the_command_line_wins_over_the_working_directory(
    main_checkout_and_a_worktree_over_the_limit, monkeypatch
):
    main_checkout, worktree = main_checkout_and_a_worktree_over_the_limit
    monkeypatch.chdir(main_checkout)

    assert cli.main(["--base", "main", "--root", str(worktree)]) == 1


def test_a_working_directory_outside_any_repository_fails_loudly(tmp_path, monkeypatch, capsys):
    outside = tmp_path / "not_a_repository"
    outside.mkdir()
    monkeypatch.chdir(outside)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))

    assert cli.main(["--base", "main"]) == 2
    assert "agent-os-quality:" in capsys.readouterr().err
