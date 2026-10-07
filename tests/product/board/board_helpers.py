"""Builders for the board tests: a fake `gh` first in PATH and a small tree. No network."""

from __future__ import annotations

import json
import os
import pathlib
import stat
import sys

# The tree tests' builders are shared, not copied.
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "tree"))

from tree_helpers import write_node

MUTATING_VERBS = {"create", "field-create", "item-create", "item-edit"}


def install_fake_gh(directory: pathlib.Path, monkeypatch, initial_state: dict | None = None):
    """Puts a `gh` in `directory` ahead of PATH; returns the state file that is all of GitHub."""
    bin_directory = directory / "fake-bin"
    bin_directory.mkdir()
    script_source = pathlib.Path(__file__).with_name("fake_gh_script.py").read_text()
    gh = bin_directory / "gh"
    gh.write_text(f"#!{sys.executable}\n{script_source}")
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    state_path = directory / "github-state.json"
    state = {"projects": [], "fields": [], "items": [], "calls": []}
    state.update(initial_state or {})
    state_path.write_text(json.dumps(state))
    monkeypatch.setenv("PATH", f"{bin_directory}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_GH_STATE", str(state_path))
    return state_path


def read_state(state_path: pathlib.Path) -> dict:
    return json.loads(state_path.read_text())


def mutating_calls(state: dict) -> list[list[str]]:
    return [call for call in state["calls"] if call[1] in MUTATING_VERBS]


def write_board_tree(root: pathlib.Path) -> None:
    """Two requirements under one goal: `fr-offline` with three parts (one carrying an open `what`
    question, one a challenge) and `fr-sync` with no use case of its own."""
    write_node(root, "goal-notes", "goal")
    write_node(root, "fr-offline", "functional-requirement", parent="goal-notes")
    write_node(root, "uc-edit", "use-case", parent="fr-offline", state="hardened")
    write_node(
        root,
        "uc-search",
        "use-case",
        parent="fr-offline",
        state="improvised",
        experiments=[
            {
                "kind": "question",
                "question": "Should search cover archived notes?",
                "outcome": "open",
                "date": "2026-10-06",
                "scope": "what",
                "default_answer": "No",
            }
        ],
    )
    write_node(
        root,
        "uc-export",
        "use-case",
        parent="fr-offline",
        challenge={"reason": "no-solution", "explanation": "no format keeps the layout"},
    )
    write_node(root, "fr-sync", "functional-requirement", parent="goal-notes", state="implemented")
