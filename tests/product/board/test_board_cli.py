"""`agent-os-tree board ...` end to end through the tree CLI, against a fake `gh`."""

from __future__ import annotations

import json

from board_helpers import install_fake_gh, mutating_calls, read_state, write_board_tree
from conftest import EXAMPLE_CONFIG

from agent_os.product.tree.cli import main


def test_board_sync_dry_run_prints_the_plan(tmp_path, monkeypatch, capsys):
    write_board_tree(tmp_path / "product")
    state_path = install_fake_gh(tmp_path, monkeypatch)
    status = main(
        ["board", "sync", "--dry-run", "--root", str(tmp_path / "product")],
        config_path=EXAMPLE_CONFIG,
    )
    assert status == 0
    assert "create item fr-offline" in capsys.readouterr().out
    assert mutating_calls(read_state(state_path)) == []


def test_board_order_writes_the_owner_order_file(tmp_path, monkeypatch, capsys):
    write_board_tree(tmp_path / "product")
    install_fake_gh(tmp_path, monkeypatch)
    root = ["--root", str(tmp_path / "product")]
    assert main(["board", "sync", *root], config_path=EXAMPLE_CONFIG) == 0
    out = tmp_path / "owner-order.json"
    assert main(["board", "order", *root, "--out", str(out)], config_path=EXAMPLE_CONFIG) == 0
    assert json.loads(out.read_text())["requirements"] == ["fr-offline", "fr-sync"]


def test_board_failure_is_one_line_and_exit_1(tmp_path, monkeypatch, capsys):
    write_board_tree(tmp_path / "product")
    monkeypatch.setenv("PATH", str(tmp_path))
    status = main(
        ["board", "sync", "--root", str(tmp_path / "product")], config_path=EXAMPLE_CONFIG
    )
    assert status == 1
    assert "gh" in capsys.readouterr().err
