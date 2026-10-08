"""`worker_task.sh <backend> init` when the worktree is gone but its branch survived.

Recreating a lost worktree used to die on git's "a branch named 'agent-os/init-<backend>' already
exists". Throwaway host root, bare local origin, no network and no backend: `init` launches nothing.
"""

from __future__ import annotations

import os
import subprocess

from agent_os.cli import AGENT_OS_DIR, host_root

DRIVER = AGENT_OS_DIR / "bin" / "worker_task.sh"
INIT_BRANCH = "agent-os/init-claude"


def _git(*arguments, cwd):
    return subprocess.run(
        ["git", *arguments], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _commit(root, name):
    (root / name).write_text(name)
    _git("add", name, cwd=root)
    _git("commit", "-qm", name, cwd=root)


class HostWithOrigin:
    def __init__(self, tmp_path):
        remote = tmp_path / "remote.git"
        subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
        self.root = tmp_path / "main_checkout"
        self.root.mkdir()
        _git("init", "-q", "-b", "main", cwd=self.root)
        _git("config", "user.email", "host@example.invalid", cwd=self.root)
        _git("config", "user.name", "host", cwd=self.root)
        (self.root / "config").mkdir()
        (self.root / "config" / "agents.yaml").write_text(
            "project:\n  repo: owner/name\n  tracking_epic: 1\n  board_number: 1\nclasses: {}\n"
        )
        _git("add", "config/agents.yaml", cwd=self.root)
        _git("commit", "-qm", "base", cwd=self.root)
        _git("remote", "add", "origin", str(remote), cwd=self.root)
        _git("push", "-q", "-u", "origin", "main", cwd=self.root)
        self.worktree = tmp_path / "worktree"
        cache = tmp_path / "cache"
        cache.mkdir()
        self.environment = {
            **os.environ,
            "AGENT_OS_HOST_ROOT": str(self.root),
            "WORKER_WORKTREE": str(self.worktree),
            "WORKER_CACHE_DIR": str(cache),
        }

    def init(self):
        return subprocess.run(
            ["bash", str(DRIVER), "claude", "init"],
            cwd=host_root(),
            env=self.environment,
            capture_output=True,
            text=True,
            check=False,
        )

    def origin_main(self):
        return _git("rev-parse", "origin/main", cwd=self.root)

    def advance_origin_main(self):
        _commit(self.root, "advance")
        _git("push", "-q", "origin", "main", cwd=self.root)


def test_a_worktree_deleted_by_hand_is_recreated_on_the_branch_that_survived(tmp_path):
    host = HostWithOrigin(tmp_path)
    assert host.init().returncode == 0
    subprocess.run(["rm", "-rf", str(host.worktree)], check=True)

    result = host.init()

    assert result.returncode == 0, result.stdout + result.stderr
    assert "created" in result.stdout
    assert _git("branch", "--show-current", cwd=host.worktree) == INIT_BRANCH
    assert _git("rev-parse", "HEAD", cwd=host.worktree) == host.origin_main()


def test_a_worktree_removed_cleanly_is_recreated_on_the_branch_that_survived(tmp_path):
    host = HostWithOrigin(tmp_path)
    assert host.init().returncode == 0
    _git("worktree", "remove", "--force", str(host.worktree), cwd=host.root)

    result = host.init()

    assert result.returncode == 0, result.stdout + result.stderr
    assert _git("branch", "--show-current", cwd=host.worktree) == INIT_BRANCH


def test_a_surviving_branch_behind_origin_main_is_brought_to_its_tip(tmp_path):
    host = HostWithOrigin(tmp_path)
    assert host.init().returncode == 0
    _git("worktree", "remove", "--force", str(host.worktree), cwd=host.root)
    host.advance_origin_main()

    result = host.init()

    assert result.returncode == 0, result.stdout + result.stderr
    assert _git("rev-parse", "HEAD", cwd=host.worktree) == host.origin_main()


def test_a_surviving_branch_with_commits_of_its_own_is_kept_and_the_message_says_what_to_do(
    tmp_path,
):
    host = HostWithOrigin(tmp_path)
    assert host.init().returncode == 0
    _commit(host.worktree, "unpublished")
    kept_tip = _git("rev-parse", "HEAD", cwd=host.worktree)
    _git("worktree", "remove", "--force", str(host.worktree), cwd=host.root)

    result = host.init()

    assert result.returncode == 1, result.stdout + result.stderr
    assert INIT_BRANCH in result.stdout and "1 commit" in result.stdout
    assert f"git -C {host.root} worktree add {host.worktree} {INIT_BRANCH}" in result.stdout
    assert f"git -C {host.root} branch -D {INIT_BRANCH}" in result.stdout
    assert _git("rev-parse", INIT_BRANCH, cwd=host.root) == kept_tip
    assert not (host.worktree / ".git").exists()


def test_a_branch_checked_out_in_another_worktree_is_refused_naming_where(tmp_path):
    host = HostWithOrigin(tmp_path)
    assert host.init().returncode == 0
    elsewhere = tmp_path / "elsewhere"
    _git("worktree", "remove", "--force", str(host.worktree), cwd=host.root)
    _git("worktree", "add", "-q", str(elsewhere), INIT_BRANCH, cwd=host.root)

    result = host.init()

    assert result.returncode == 1, result.stdout + result.stderr
    assert str(elsewhere) in result.stdout and INIT_BRANCH in result.stdout
    assert not (host.worktree / ".git").exists()
