"""What an ancestor's experiments hand down: the findings reach the slice, `--json` and the ticket.

Pure filesystem under `tmp_path`.
"""

from __future__ import annotations

import json
import pathlib

from compile_support import one_ticket
from tree_helpers import experiment_entry, write_node, write_sound_tree

from agent_os.product.tree.loader import load_tree
from agent_os.product.tree.slicing import build_slice, render_slice_json, render_slice_markdown


def markdown(root: pathlib.Path, node_id: str) -> str:
    return render_slice_markdown(build_slice(load_tree(root), node_id))


def write_tree_with_answered_requirement(root: pathlib.Path) -> None:
    write_sound_tree(root)
    write_node(
        root,
        "fr-offline",
        "functional-requirement",
        parent="goal-notes",
        experiments=[
            {
                "kind": "question",
                "question": "How long may a title be?",
                "outcome": "answered",
                "date": "2026-10-04",
                "scope": "what",
                "default_answer": "none",
                "finding": "At most 100 characters.",
            },
            {
                "kind": "spike",
                "question": "Does the browser notify offline?",
                "outcome": "open",
                "date": "2026-10-04",
            },
        ],
    )
    write_node(
        root,
        "fr-sibling",
        "functional-requirement",
        parent="goal-notes",
        experiments=[
            {
                "kind": "lookup",
                "question": "A sibling question",
                "outcome": "feasible",
                "date": "2026-10-04",
                "finding": "Sibling finding.",
            }
        ],
    )


def test_the_slice_carries_the_findings_of_the_ancestors_experiments(tmp_path):
    write_tree_with_answered_requirement(tmp_path)
    text = markdown(tmp_path, "uc-edit")
    assert "question: How long may a title be? -- At most 100 characters." in text
    assert "Does the browser notify offline?" not in text, "an open experiment found nothing"
    assert "Sibling finding." not in text


def test_the_json_slice_carries_the_findings_of_each_ancestor(tmp_path):
    write_tree_with_answered_requirement(tmp_path)
    data = json.loads(render_slice_json(build_slice(load_tree(tmp_path), "uc-edit")))
    (requirement,) = [a for a in data["ancestors"] if a["id"] == "fr-offline"]
    assert requirement["experiments"] == [
        {
            "kind": "question",
            "question": "How long may a title be?",
            "finding": "At most 100 characters.",
        }
    ]


def test_a_ticket_carries_the_findings_of_its_requirements_experiments(tmp_path):
    write_sound_tree(tmp_path)
    write_node(
        tmp_path,
        "fr-offline",
        "functional-requirement",
        parent="goal-notes",
        experiments=[experiment_entry("feasible", kind="lookup", question="Which stack?")],
    )
    assert "Which stack? -- f" in one_ticket(tmp_path, "uc-edit").body
