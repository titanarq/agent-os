"""`agent-os-tree` end to end: exit statuses, the lines it prints, and where its root comes from.

The command runs in this process (`main(argv, config_path=...)`) with a config of the test's own,
and once as a real `python -m agent_os.tree` subprocess to prove the module form works. No
network, no `gh`, no backend.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest
import yaml
from conftest import EXAMPLE_CONFIG
from tree_helpers import write_node, write_sound_tree

from agent_os.cli import AGENT_OS_DIR
from agent_os.tree.cli import main


def run(argv, *, config_path=EXAMPLE_CONFIG):
    return main([str(part) for part in argv], config_path=config_path)


def config_with_tree(tmp_path: pathlib.Path, **tree_keys) -> pathlib.Path:
    data = yaml.safe_load(EXAMPLE_CONFIG.read_text())
    data["tree"] = tree_keys
    path = tmp_path / "agents.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return path


# --------------------------------------------------------------------------------------------
# validate / doctor
# --------------------------------------------------------------------------------------------


def test_validate_on_a_sound_tree_prints_ok_and_exits_zero(tmp_path, capsys):
    write_sound_tree(tmp_path)
    assert run(["validate", "--root", tmp_path]) == 0
    assert capsys.readouterr().out.startswith("ok: 3 node(s), 1 decision(s) under ")


def test_validate_prints_one_line_per_defect_with_the_file_path_and_exits_one(
    tmp_path, capsys, monkeypatch
):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "uc-orphan", "use-case", parent="fr-gone")
    (tmp_path / "stray.txt").write_text("x")
    monkeypatch.chdir(tmp_path)
    assert run(["validate", "--root", "."]) == 1
    lines = capsys.readouterr().out.splitlines()
    assert lines[:2] == [
        "stray.txt: orphan-file: not a Markdown file, so neither a node nor a decision",
        "uc-orphan.md: dangling-parent: parent 'fr-gone': no such node",
    ]
    assert lines[2] == "FAIL: 2 defect(s) in 2 file(s) under ."


def test_doctor_is_the_same_command_as_validate(tmp_path, capsys):
    write_sound_tree(tmp_path)
    (tmp_path / "stray.txt").write_text("x")
    assert run(["doctor", "--root", tmp_path]) == 1
    assert "orphan-file" in capsys.readouterr().out


def test_validate_json_lists_every_defect(tmp_path, capsys):
    write_sound_tree(tmp_path)
    (tmp_path / "stray.txt").write_text("x")
    assert run(["validate", "--root", tmp_path, "--json"]) == 1
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] is False
    assert data["nodes"] == 3 and data["decisions"] == 1
    assert [d["check"] for d in data["defects"]] == ["orphan-file"]
    assert data["defects"][0]["path"].endswith("stray.txt")


def test_validate_json_of_a_sound_tree_is_ok(tmp_path, capsys):
    write_sound_tree(tmp_path)
    assert run(["validate", "--root", tmp_path, "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] is True and data["defects"] == []


# --------------------------------------------------------------------------------------------
# context
# --------------------------------------------------------------------------------------------


def test_context_prints_the_slice(tmp_path, capsys):
    write_sound_tree(tmp_path)
    assert run(["context", "uc-edit", "--root", tmp_path]) == 0
    out = capsys.readouterr().out
    assert out.startswith("# Slice of `uc-edit`\n")
    assert "`dec-local-first`" in out


def test_context_json_prints_the_slice_as_data(tmp_path, capsys):
    write_sound_tree(tmp_path)
    assert run(["context", "uc-edit", "--root", tmp_path, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["node"]["id"] == "uc-edit"


def test_context_of_an_unknown_node_says_so_on_stderr_and_exits_one(tmp_path, capsys):
    write_sound_tree(tmp_path)
    assert run(["context", "uc-ghost", "--root", tmp_path]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "no node 'uc-ghost'" in captured.err


def test_context_over_a_defective_slice_prints_the_doctors_lines_on_stderr(tmp_path, capsys):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "uc-edit", "use-case", parent="fr-offline", state="hardened")
    assert run(["context", "uc-edit", "--root", tmp_path]) == 1
    err = capsys.readouterr().err
    assert "hardened-needs-implementation" in err and "hardened-needs-verification" in err


# --------------------------------------------------------------------------------------------
# compile
# --------------------------------------------------------------------------------------------


def test_compile_prints_tickets_and_escalations_and_creates_nothing(tmp_path, capsys):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "uc-vague", "use-case", parent="fr-offline")
    assert run(["compile", "--root", tmp_path]) == 0
    out = capsys.readouterr().out
    assert out.startswith("compiled 1 ticket(s), 1 escalation(s)")
    assert "<!-- budget: mechanical-qwen -->" in out
    assert "<!-- node: uc-edit -->" in out
    assert "uc-vague" in out.split("=== escalation: uc-vague ===")[1]


def test_compile_json(tmp_path, capsys):
    write_sound_tree(tmp_path)
    assert run(["compile", "--root", tmp_path, "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert [t["node"] for t in data["tickets"]] == ["uc-edit"]


def test_compile_out_dir_writes_the_bodies_and_the_index(tmp_path, capsys):
    tree = tmp_path / "tree"
    tree.mkdir()
    write_sound_tree(tree)
    out_dir = tmp_path / "out"
    assert run(["compile", "--root", tree, "--out-dir", out_dir]) == 0
    assert sorted(p.name for p in out_dir.iterdir()) == ["compile.json", "uc-edit.md"]
    assert "<!-- node: uc-edit -->" in (out_dir / "uc-edit.md").read_text()
    assert "wrote" in capsys.readouterr().err


def test_compile_takes_the_budget_class_and_labels_from_its_flags(tmp_path, capsys):
    write_sound_tree(tmp_path)
    assert (
        run(
            [
                "compile",
                "--root",
                tmp_path,
                "--json",
                "--budget-class",
                "complex-qwen",
                "--label",
                "p2",
                "--label",
                "module:core",
            ]
        )
        == 0
    )
    (ticket,) = json.loads(capsys.readouterr().out)["tickets"]
    assert ticket["budget_class"] == "complex-qwen"
    assert ticket["labels"] == ["type:task", "p2", "module:core"]


def test_compile_without_any_budget_class_refuses(tmp_path, capsys):
    tree = tmp_path / "tree"
    tree.mkdir()
    write_sound_tree(tree)
    config = config_with_tree(tmp_path)
    assert run(["compile", "--root", tree], config_path=config) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "no budget class for the tickets" in captured.err


def test_compile_uses_the_configured_class_when_no_flag_is_given(tmp_path, capsys):
    tree = tmp_path / "tree"
    tree.mkdir()
    write_sound_tree(tree)
    config = config_with_tree(tmp_path, ticket_budget_class="complex-qwen")
    assert run(["compile", "--root", tree, "--json"], config_path=config) == 0
    assert json.loads(capsys.readouterr().out)["tickets"][0]["budget_class"] == "complex-qwen"


def test_compile_of_a_red_tree_prints_why_on_stderr_and_exits_one(tmp_path, capsys):
    write_sound_tree(tmp_path)
    (tmp_path / "stray.txt").write_text("x")
    assert run(["compile", "--root", tmp_path]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "fails the doctor" in captured.err and "orphan-file" in captured.err


def test_compile_with_an_unreadable_config_says_what_it_needs_the_config_for(tmp_path, capsys):
    write_sound_tree(tmp_path)
    assert run(["compile", "--root", tmp_path], config_path=tmp_path / "missing.yaml") == 1
    assert "compile needs the config" in capsys.readouterr().err


# --------------------------------------------------------------------------------------------
# The root
# --------------------------------------------------------------------------------------------


def test_the_root_comes_from_the_configs_tree_root_when_no_flag_is_given(tmp_path, capsys):
    tree = tmp_path / "somewhere"
    tree.mkdir()
    write_sound_tree(tree)
    # An absolute `tree.root` is taken as it is: relative ones are joined to the host's root.
    config = config_with_tree(tmp_path, root=str(tree))
    assert run(["validate"], config_path=config) == 0
    assert "ok: 3 node(s)" in capsys.readouterr().out


def test_a_root_that_is_not_a_directory_is_an_error_not_an_empty_tree(tmp_path, capsys):
    assert run(["validate", "--root", tmp_path / "nope"]) == 1
    assert "is not a directory" in capsys.readouterr().err


def test_a_configured_root_that_is_missing_fails_loudly(tmp_path, capsys):
    config = config_with_tree(tmp_path, root=str(tmp_path / "nope"))
    assert run(["validate"], config_path=config) == 1
    assert "is not a directory" in capsys.readouterr().err


def test_no_flag_and_no_readable_config_is_an_error_and_never_a_default_directory(tmp_path, capsys):
    assert run(["validate"], config_path=tmp_path / "missing.yaml") == 1
    err = capsys.readouterr().err
    assert "no --root given and the tree root cannot be read from the config" in err


def test_a_usage_error_exits_two():
    with pytest.raises(SystemExit) as raised:
        run(["context"])
    assert raised.value.code == 2


def test_the_module_form_runs_as_a_real_process(tmp_path):
    write_sound_tree(tmp_path)
    # Stub-free on purpose: the module touches no backend, so there is nothing to put first in PATH.
    done = subprocess.run(
        [sys.executable, "-m", "agent_os.tree", "validate", "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
        cwd=AGENT_OS_DIR,
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.startswith("ok: 3 node(s), 1 decision(s)")
    (tmp_path / "stray.txt").write_text("x")
    red = subprocess.run(
        [sys.executable, "-m", "agent_os.tree", "doctor", "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
        cwd=AGENT_OS_DIR,
    )
    assert red.returncode == 1
    assert "orphan-file" in red.stdout
