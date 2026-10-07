"""`worker_task.sh start` in a v2 host refuses what the tree rules refuse, and says why.

A throwaway worktree, a stub `gh` and a fake `claude` first in `PATH`: no network, no backend.
"""

from __future__ import annotations

import json
import os
import subprocess

import pytest
from compile_support import compiled, write_v2_config
from tree_helpers import write_node, write_sound_tree

from agent_os.cli import AGENT_OS_DIR, host_root

DRIVER = AGENT_OS_DIR / "bin" / "worker_task.sh"

GH_STUB = """#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
if args[:2] == ["issue", "list"]:
    print(os.environ["GH_STUB_OPEN_ISSUES"])
    sys.exit(0)
if args[:2] == ["issue", "view"]:
    print(os.environ["GH_STUB_BODY"] if "-q" in args else json.dumps(
        {"body": os.environ["GH_STUB_BODY"], "labels": [], "state": "OPEN"}))
    sys.exit(0)
path = args[1].split("/") if args[:1] == ["api"] and len(args) > 1 else []
if len(path) == 5 and path[3] == "issues":
    print(json.dumps({"body": os.environ["GH_STUB_BODY"], "number": int(path[4])}))
    sys.exit(0)
if args[:1] == ["api"]:
    print(json.dumps({"number": 1}))
    sys.exit(0)
print("unexpected gh call: " + " ".join(args), file=sys.stderr)
sys.exit(3)
"""
FAKE_CLAUDE = "#!/bin/sh\necho 'a fake claude must never run in this test' >&2\nexit 97\n"


@pytest.fixture
def driver_environment(tmp_path):
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(worktree)], check=True)
    binaries = tmp_path / "bin"
    binaries.mkdir()
    for name, text in (("gh", GH_STUB), ("claude", FAKE_CLAUDE)):
        (binaries / name).write_text(text)
        (binaries / name).chmod(0o755)
    environment = dict(os.environ)
    environment.update(
        PATH=f"{binaries}:{environment['PATH']}",
        WORKER_WORKTREE=str(worktree),
        WORKER_CACHE_DIR=str(tmp_path / "cache"),
        AGENT_OS_GH_REPO="owner/name",
        AGENTS_CONFIG_PATH=str(write_v2_config(tmp_path / "agents.yaml")),
    )
    return environment


def start(environment, issue):
    return subprocess.run(
        ["bash", str(DRIVER), "claude", "start", str(issue)],
        cwd=host_root(),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def ticket_body(tmp_path, *, depends_on):
    tree = tmp_path / "tree"
    write_sound_tree(tree)
    write_node(
        tree,
        "uc-sync",
        "use-case",
        parent="fr-offline",
        verification=[{"command": "true"}],
        depends_on=depends_on,
    )
    return next(t.body for t in compiled(tree).tickets if t.node_id == "uc-sync")


def test_start_refuses_a_ticket_whose_dependency_is_still_open(driver_environment, tmp_path):
    driver_environment["GH_STUB_BODY"] = ticket_body(tmp_path, depends_on=["uc-edit"])
    driver_environment["GH_STUB_OPEN_ISSUES"] = json.dumps(
        [
            {"number": 346, "body": "<!-- node: uc-edit -->"},
            {"number": 347, "body": driver_environment["GH_STUB_BODY"]},
        ]
    )
    result = start(driver_environment, 347)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "refusing to dispatch: issue #347: it depends on node `uc-edit`" in result.stderr


def test_start_goes_past_the_tree_rules_when_nothing_stands_in_the_way(
    driver_environment, tmp_path
):
    driver_environment["GH_STUB_BODY"] = ticket_body(tmp_path, depends_on=["uc-edit"])
    driver_environment["GH_STUB_OPEN_ISSUES"] = json.dumps(
        [{"number": 347, "body": driver_environment["GH_STUB_BODY"]}]
    )
    result = start(driver_environment, 347)
    assert "it depends on node" not in result.stderr
    assert "no node address" not in result.stderr
