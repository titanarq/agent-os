"""The guard's dispatchable scan and the worker's brief in a v2 host.

`gh` is a function returning rows; the tree is a directory under `tmp_path`. No network, no backend.
"""

from __future__ import annotations

import json
import subprocess

import pytest
from compile_support import CONFIG, compiled, write_v2_config
from tree_helpers import write_node, write_sound_tree

from agent_os import guard as agent_guard
from agent_os import lib
from agent_os.product.dispatch.brief_slice import brief_slice_section


def completed(cmd, rows):
    return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(rows), stderr="")


def ready_row(number, body):
    return {
        "number": number,
        "state": "OPEN",
        "labels": [{"name": agent_guard.READY_LABEL}],
        "body": body,
    }


@pytest.fixture
def v2_host(monkeypatch, tmp_path):
    monkeypatch.setattr(lib, "DEFAULT_AGENTS_CONFIG", write_v2_config(tmp_path / "agents.yaml"))
    monkeypatch.setattr(agent_guard, "load_task_classes", lambda: CONFIG.classes)
    monkeypatch.setattr(agent_guard, "backend_has_a_worktree", lambda backend: True)
    monkeypatch.setattr(agent_guard, "backend_dispatch_dirt", lambda backend, *, main: [])


def tickets_of_a_tree(tmp_path):
    tree = tmp_path / "tree"
    write_sound_tree(tree)
    write_node(
        tree,
        "uc-sync",
        "use-case",
        parent="fr-offline",
        verification=[{"command": "true"}],
        depends_on=["uc-edit"],
    )
    return {t.node_id: t.body for t in compiled(tree).tickets}


def test_the_scan_leaves_out_what_has_no_address_or_an_open_dependency(
    v2_host, monkeypatch, tmp_path
):
    bodies = tickets_of_a_tree(tmp_path)
    ready = [
        ready_row(1, bodies["uc-edit"]),
        ready_row(2, bodies["uc-sync"]),
        ready_row(3, bodies["uc-edit"].replace("<!-- node: uc-edit -->", "")),
    ]

    monkeypatch.setattr(agent_guard.subprocess, "run", lambda cmd, **kw: completed(cmd, ready))
    assert agent_guard.dispatchable_scan(main=tmp_path).issues == [1]


def test_the_scan_lets_a_dependent_through_once_its_dependency_is_closed(
    v2_host, monkeypatch, tmp_path
):
    bodies = tickets_of_a_tree(tmp_path)
    ready = [ready_row(2, bodies["uc-sync"])]
    monkeypatch.setattr(agent_guard.subprocess, "run", lambda cmd, **kw: completed(cmd, ready))
    assert agent_guard.dispatchable_scan(main=tmp_path).issues == [2]


def test_the_brief_of_a_ticket_carries_the_slice_of_its_node_and_not_the_tree(
    monkeypatch, tmp_path
):
    bodies = tickets_of_a_tree(tmp_path)
    monkeypatch.setattr(lib, "DEFAULT_AGENTS_CONFIG", write_v2_config(tmp_path / "agents.yaml"))
    monkeypatch.setattr("agent_os.product.dispatch.brief_slice.host_root", lambda: tmp_path)
    config = tmp_path / "agents.yaml"
    config.write_text(config.read_text().replace("root: product", "root: tree"))
    section = brief_slice_section(bodies["uc-sync"])
    assert "## Slice of node `uc-sync`" in section
    assert "fr-offline" in section and "goal-notes" in section
    assert "Description of uc-edit." not in section
    assert brief_slice_section("a body with no address") == ""


def test_no_slice_is_added_outside_a_v2_host(monkeypatch, tmp_path):
    bodies = tickets_of_a_tree(tmp_path)
    monkeypatch.setattr(
        lib, "DEFAULT_AGENTS_CONFIG", write_v2_config(tmp_path / "a.yaml", dispatch_by_node=False)
    )
    assert brief_slice_section(bodies["uc-sync"]) == ""
