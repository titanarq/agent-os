"""The `Node-Change` trailer check: every commit that touches the tree carries one valid trailer.

Real git repositories under `tmp_path`, no network, no backend.
"""

from __future__ import annotations

import json
import pathlib
import subprocess

import pytest
from conftest import EXAMPLE_CONFIG

from agent_os.product.tree.cli import main
from agent_os.product.tree.trailers import (
    MISPLACED_TRAILER,
    MISSING_TRAILER,
    MULTIPLE_TRAILERS,
    UNKNOWN_VALUE,
    TrailerError,
    check_node_change_trailers,
)

GIT_IDENTITY = ["-c", "user.name=Test", "-c", "user.email=test@example.invalid"]


def git(repository: pathlib.Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *GIT_IDENTITY, *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def commit_file(repository: pathlib.Path, relative: str, message: str) -> None:
    path = repository / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{message}\n{path.read_text() if path.exists() else ''}")
    git(repository, "add", relative)
    git(repository, "commit", "-q", "-m", message)


@pytest.fixture
def repository(tmp_path) -> pathlib.Path:
    git(tmp_path, "init", "-q", "-b", "main")
    commit_file(tmp_path, "README.md", "base")
    git(tmp_path, "tag", "base")
    return tmp_path


def defect_codes(repository: pathlib.Path) -> list[str]:
    defects = check_node_change_trailers(repository / "product", "base", "HEAD")
    return [defect.code for defect in defects]


def test_a_commit_outside_the_tree_needs_no_trailer(repository):
    commit_file(repository, "src/code.py", "feat: code")
    (repository / "product").mkdir()
    assert defect_codes(repository) == []


@pytest.mark.parametrize("value", ["usage", "rework", "owner"])
def test_a_commit_in_the_tree_with_a_valid_trailer_passes(repository, value):
    commit_file(repository, "product/goal-a.md", f"tree: edit\n\nNode-Change: {value}")
    assert defect_codes(repository) == []


def test_a_commit_in_the_tree_without_a_trailer_is_a_defect(repository):
    commit_file(repository, "product/goal-a.md", "tree: edit")
    assert defect_codes(repository) == [MISSING_TRAILER]


def test_an_unknown_value_is_a_defect(repository):
    commit_file(repository, "product/goal-a.md", "tree: edit\n\nNode-Change: whim")
    assert defect_codes(repository) == [UNKNOWN_VALUE]


def test_two_trailers_are_a_defect_even_when_both_are_valid(repository):
    commit_file(
        repository, "product/goal-a.md", "tree: edit\n\nNode-Change: usage\nNode-Change: owner"
    )
    assert defect_codes(repository) == [MULTIPLE_TRAILERS]


def test_a_commit_mixing_tree_and_code_files_still_needs_the_trailer(repository):
    path = repository / "src" / "code.py"
    path.parent.mkdir()
    path.write_text("x")
    commit_file(repository, "product/goal-a.md", "tree: edit")
    git(repository, "reset", "-q", "--soft", "HEAD~1")
    git(repository, "add", "src/code.py")
    git(repository, "commit", "-q", "-m", "tree and code")
    assert defect_codes(repository) == [MISSING_TRAILER]


def test_a_trailer_cut_off_from_the_last_paragraph_is_named_as_misplaced_not_as_missing(repository):
    """git reads only the LAST paragraph as trailers, so a `Node-Change:` line followed by a blank
    line and a `Co-Authored-By:` line is invisible to it -- and 'missing' would send whoever reads
    the report looking for a line that is right there."""
    commit_file(
        repository,
        "product/goal-a.md",
        "tree: edit\n\nNode-Change: usage\n\nCo-Authored-By: Someone <noreply@example.invalid>",
    )
    assert defect_codes(repository) == [MISPLACED_TRAILER]


def test_a_trailer_in_the_same_block_as_the_co_author_line_passes(repository):
    commit_file(
        repository,
        "product/goal-a.md",
        "tree: edit\n\nNode-Change: usage\nCo-Authored-By: Someone <noreply@example.invalid>",
    )
    assert defect_codes(repository) == []


def test_only_the_range_is_checked(repository):
    commit_file(repository, "product/old.md", "old edit without a trailer")
    git(repository, "tag", "later-base")
    commit_file(repository, "product/new.md", "new\n\nNode-Change: rework")
    defects = check_node_change_trailers(repository / "product", "later-base", "HEAD")
    assert defects == []


def test_a_range_git_cannot_resolve_fails_loudly(repository):
    with pytest.raises(TrailerError):
        check_node_change_trailers(repository / "product", "no-such-ref", "HEAD")


def test_a_tree_root_outside_a_git_repository_fails_loudly(tmp_path):
    with pytest.raises(TrailerError):
        check_node_change_trailers(tmp_path / "product", "base", "HEAD")


def test_the_subcommand_reports_each_defect_and_exits_one(repository, capsys):
    commit_file(repository, "product/goal-a.md", "tree: edit")
    status = main(
        ["trailers", "--base", "base", "--root", str(repository / "product")],
        config_path=EXAMPLE_CONFIG,
    )
    output = capsys.readouterr().out
    assert status == 1
    assert f"{MISSING_TRAILER}: " in output and "tree: edit" in output


def test_the_subcommand_exits_zero_on_a_sound_range(repository, capsys):
    commit_file(repository, "product/goal-a.md", "tree: edit\n\nNode-Change: usage")
    status = main(
        ["trailers", "--base", "base", "--root", str(repository / "product"), "--json"],
        config_path=EXAMPLE_CONFIG,
    )
    assert status == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_the_subcommand_exits_one_with_a_message_on_a_bad_range(repository, capsys):
    status = main(
        ["trailers", "--base", "nope", "--root", str(repository / "product")],
        config_path=EXAMPLE_CONFIG,
    )
    assert status == 1
    assert "agent-os-tree:" in capsys.readouterr().err
