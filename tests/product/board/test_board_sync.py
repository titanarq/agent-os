"""Sync and order against a fake `gh`: never the network."""

from __future__ import annotations

import json

import pytest
from board_helpers import install_fake_gh, mutating_calls, read_state, write_board_tree

from agent_os.lib import BoardConfig
from agent_os.product.board.order import read_owner_order
from agent_os.product.board.project import BoardError, GhProjectClient
from agent_os.product.board.sync import sync_board
from agent_os.product.tree.loader import load_tree

CONFIG = BoardConfig(owner="acme")


@pytest.fixture
def github(tmp_path, monkeypatch):
    tree_root = tmp_path / "product"
    write_board_tree(tree_root)
    state_path = install_fake_gh(tmp_path, monkeypatch)
    return tree_root, state_path


def run_sync(tree_root, *, dry_run=False, config=CONFIG):
    return sync_board(load_tree(tree_root), GhProjectClient(config.owner), config, dry_run=dry_run)


def test_a_dry_run_changes_nothing_and_says_what_it_would_do(github):
    tree_root, state_path = github
    plan = run_sync(tree_root, dry_run=True)
    assert mutating_calls(read_state(state_path)) == []
    lines = plan.describe()
    assert "create project 'Agentos progress board'" in lines[0]
    assert any("create item fr-offline" in line for line in lines)
    assert any("create field Progress" in line for line in lines)


def test_the_first_sync_creates_the_project_the_fields_and_one_item_per_requirement(github):
    tree_root, state_path = github
    run_sync(tree_root)
    state = read_state(state_path)
    assert [p["title"] for p in state["projects"]] == ["Agentos progress board"]
    assert {f["name"] for f in state["fields"]} == {"Progress", "Order"}
    by_title = {item["content"]["body"].split("-->")[0]: item for item in state["items"]}
    assert len(state["items"]) == 2
    offline = by_title["<!-- agent-os-board: fr-offline "]
    assert offline["progress"] == "pending 1 | improvised 1 | implemented 0 | hardened 1"


def test_a_second_sync_makes_no_change(github):
    tree_root, state_path = github
    run_sync(tree_root)
    calls_after_first = len(read_state(state_path)["calls"])
    plan = run_sync(tree_root)
    state = read_state(state_path)
    assert plan.is_empty
    assert mutating_calls({"calls": state["calls"][calls_after_first:]}) == []


def test_a_changed_state_rewrites_the_item_in_place(github):
    tree_root, state_path = github
    run_sync(tree_root)
    search = tree_root / "uc-search.md"
    search.write_text(search.read_text().replace("state: improvised", "state: hardened"))
    run_sync(tree_root)
    state = read_state(state_path)
    offline = next(i for i in state["items"] if "fr-offline" in i["content"]["body"])
    assert len(state["items"]) == 2
    assert offline["progress"].endswith("hardened 2")
    assert "[hardened] uc-search" in offline["content"]["body"]


def test_an_item_whose_requirement_left_the_tree_is_reported_and_kept(github):
    tree_root, state_path = github
    run_sync(tree_root)
    (tree_root / "fr-sync.md").unlink()
    plan = run_sync(tree_root)
    assert any("orphan" in line and "fr-sync" in line for line in plan.describe())
    assert len(read_state(state_path)["items"]) == 2


def test_a_pinned_project_number_is_used_and_never_created(tmp_path, monkeypatch):
    tree_root = tmp_path / "product"
    write_board_tree(tree_root)
    state_path = install_fake_gh(
        tmp_path, monkeypatch, {"projects": [{"number": 7, "id": "PVT_7", "title": "Mine"}]}
    )
    run_sync(tree_root, config=BoardConfig(owner="acme", number=7))
    assert len(read_state(state_path)["projects"]) == 1
    assert len(read_state(state_path)["items"]) == 2


def test_the_owner_order_comes_from_the_order_field_and_unordered_follow_in_tree_order(github):
    tree_root, state_path = github
    run_sync(tree_root)
    state = read_state(state_path)
    next(i for i in state["items"] if "fr-sync" in i["content"]["body"])["order"] = 1.0
    state_path.write_text(json.dumps(state))
    owner_order = read_owner_order(load_tree(tree_root), GhProjectClient("acme"), CONFIG)
    assert owner_order.ordered == ["fr-sync"]
    assert owner_order.unordered == ["fr-offline"]
    assert owner_order.requirement_ids == ["fr-sync", "fr-offline"]


def test_a_failing_gh_is_an_error_with_its_message(tmp_path, monkeypatch):
    install_fake_gh(tmp_path, monkeypatch)
    with pytest.raises(BoardError, match="no such project"):
        GhProjectClient("acme").view_project(99)
