"""`agent-os-quality` against throwaway git repositories: the merge-base, the exit codes, the
config. No network and no backend."""

import pathlib
import subprocess

import pytest
import yaml

from agent_os.quality import cli
from agent_os.quality.git_snapshots import count_lines


def git(repository: pathlib.Path, *arguments: str) -> None:
    subprocess.run(
        ["git", "-C", str(repository), "-c", "user.name=t", "-c", "user.email=t@t", *arguments],
        check=True,
        capture_output=True,
    )


def write(repository: pathlib.Path, path: str, line_count: int) -> None:
    target = repository / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("x\n" * line_count)


def commit_all(repository: pathlib.Path, message: str) -> None:
    git(repository, "add", "-A")
    git(repository, "commit", "-q", "-m", message)


@pytest.fixture
def repository(tmp_path):
    root = tmp_path / "repository"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    write(root, "small.py", 5)
    write(root, "big.py", 400)
    commit_all(root, "base")
    git(root, "checkout", "-q", "-b", "feature")
    return root


def run(repository, *extra):
    return cli.main(["--base", "main", "--root", str(repository), *extra])


def test_a_branch_that_adds_nothing_wrong_passes(repository, capsys):
    write(repository, "small.py", 6)
    commit_all(repository, "grow a small file")
    assert run(repository) == 0
    assert capsys.readouterr().out == ""


def test_growing_a_file_already_over_the_limit_fails_and_names_it(repository, capsys):
    write(repository, "big.py", 401)
    commit_all(repository, "grow the big file")
    assert run(repository) == 1
    assert capsys.readouterr().out.startswith("big.py: 401 lines, was 400 on the base")


def test_a_new_file_over_the_limit_fails_and_shrinking_the_old_one_passes(repository, capsys):
    write(repository, "big.py", 399)
    write(repository, "fresh.py", 301)
    commit_all(repository, "split badly")
    assert run(repository) == 1
    assert capsys.readouterr().out.startswith("fresh.py: new, 301 lines")


def test_uncommitted_changes_are_measured_too(repository):
    write(repository, "fresh.py", 301)
    git(repository, "add", "fresh.py")
    assert run(repository) == 1


def test_the_base_is_the_merge_base_not_the_moved_tip_of_the_base_branch(repository):
    git(repository, "checkout", "-q", "main")
    write(repository, "big.py", 500)
    commit_all(repository, "main moves on")
    git(repository, "checkout", "-q", "feature")
    write(repository, "small.py", 6)
    commit_all(repository, "feature")
    assert run(repository) == 0


def test_an_unknown_base_is_an_exit_two_that_says_what_to_do(repository, capsys):
    assert cli.main(["--base", "nowhere", "--root", str(repository)]) == 2
    assert "fetch-depth: 0" in capsys.readouterr().err


def write_config(path: pathlib.Path, **sections) -> pathlib.Path:
    """The documented example config with some sections replaced: a minimal one would not load."""
    example = yaml.safe_load((cli.AGENT_OS_DIR / "config.example.yaml").read_text())
    path.write_text(yaml.safe_dump({**example, **sections}))
    return path


def test_the_configured_limits_and_excluded_paths_apply(repository, tmp_path):
    config = write_config(
        tmp_path / "agents.yaml", quality={"max_lines_per_file": 2, "excluded_paths": ["big.py"]}
    )
    write(repository, "small.py", 6)
    commit_all(repository, "grow")
    assert run(repository, "--config", str(config)) == 1


def test_the_tree_root_from_the_config_is_excluded(repository, tmp_path):
    config = write_config(tmp_path / "agents.yaml", tree={"root": "product"})
    write(repository, "product/node.md", 900)
    commit_all(repository, "a long node")
    assert run(repository, "--config", str(config)) == 0
    write(repository, "elsewhere/node.md", 900)
    commit_all(repository, "a long file outside the tree")
    assert run(repository, "--config", str(config)) == 1


def test_the_hosts_own_config_file_is_not_measured_even_when_it_replaces_the_default_exclusions(
    repository,
):
    (repository / "config").mkdir()
    config = write_config(
        repository / "config" / "agents.yaml",
        quality={"max_lines_per_file": 100, "excluded_paths": ["somewhere/else"]},
    )
    assert count_lines(config.read_bytes()) > 100
    commit_all(repository, "adopt: the generated host config")
    assert run(repository, "--config", str(config)) == 0
    write(repository, "elsewhere.py", 101)
    commit_all(repository, "a long file that is code")
    assert run(repository, "--config", str(config)) == 1


def test_a_missing_explicit_config_is_an_exit_two(repository, tmp_path):
    assert run(repository, "--config", str(tmp_path / "absent.yaml")) == 2


def test_a_mechanism_vendored_below_the_repository_is_excluded(tmp_path, monkeypatch):
    assert cli.mechanism_directory_inside(cli.AGENT_OS_DIR) is None
    assert cli.mechanism_directory_inside(cli.AGENT_OS_DIR.parent) == cli.AGENT_OS_DIR.name


def test_binary_content_counts_no_lines():
    assert count_lines(b"\0\n\n\n") == 0
