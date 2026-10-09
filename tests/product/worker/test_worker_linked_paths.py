"""A link the driver made itself is not work the worker left behind (stage1i, #3).

`init` links `project.worktree_links` (`.venv`, `.env` by default) into a new worktree. A host's
`.gitignore` of `.venv/` -- with the slash -- ignores a directory and not a symlink, which git sees
as a file, so every new slot worktree showed `?? .venv` and `branch` and `start` refused it as dirty.
`.env` already had its exemption (#404); every linked path gets the same one, in the dirty check and
in the freeze that must not commit it either. No backend is launched: only `branch` and `freeze`.
"""

from __future__ import annotations

import subprocess

from test_worker_task import DRIVER, ROOT, _git, _staged_environment, _subjects


def _driver(environment, *arguments):
    return subprocess.run(
        ["bash", str(DRIVER), "claude", *arguments],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def _git_output(*arguments, cwd):
    return subprocess.run(
        ["git", *arguments], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


def _worktree_ignoring_venv_directories(tmp_path):
    environment, _cache, worktree, tmp = _staged_environment(
        tmp_path, stage_titles=("Only stage",), mode="hang"
    )
    (worktree / ".gitignore").write_text(".venv/\n")
    _git("add", ".gitignore", cwd=worktree)
    _git("commit", "-qm", "ignore the venv directory", cwd=worktree)
    _git("push", "-q", "origin", "main:main", cwd=worktree)
    return environment, worktree, tmp


def test_a_venv_link_the_driver_made_does_not_refuse_branch(tmp_path):
    environment, worktree, tmp = _worktree_ignoring_venv_directories(tmp_path)
    (tmp / "main_venv").mkdir()
    (worktree / ".venv").symlink_to(tmp / "main_venv")
    assert "?? .venv" in _git_output("status", "--porcelain", cwd=worktree)
    result = _driver(environment, "branch", "task/347-staged-again")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "is now on task/347-staged-again" in result.stdout


def test_a_venv_that_is_not_a_link_is_still_work_the_worker_left(tmp_path):
    environment, worktree, _tmp = _worktree_ignoring_venv_directories(tmp_path)
    (worktree / ".venv").write_text("a file a worker wrote\n")
    result = _driver(environment, "branch", "task/347-staged-again")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "worktree is dirty" in result.stdout and "?? .venv" in result.stdout


def test_the_freeze_does_not_commit_a_venv_link(tmp_path):
    environment, worktree, tmp = _worktree_ignoring_venv_directories(tmp_path)
    (tmp / "main_venv").mkdir()
    (worktree / ".venv").symlink_to(tmp / "main_venv")
    (worktree / "README.md").write_text("changed by the cut run\n")
    (worktree / "new_file.txt").write_text("a file the stage never added\n")
    result = _driver(environment, "freeze", "stall")
    assert result.returncode == 0, result.stdout + result.stderr
    assert _subjects(worktree)[0] == "WIP: cut by guard (stall)"
    frozen = _git_output("show", "--name-only", "--format=", "HEAD", cwd=worktree).split()
    assert sorted(frozen) == ["README.md", "new_file.txt"], frozen
