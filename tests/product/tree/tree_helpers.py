"""Builders for the tree tests: write a node or a decision file under a tmp root, field by field.

Imported by name (`from tree_helpers import write_node`), the way `conftest` is: pytest puts this
directory on `sys.path` for its own collection. Nothing here reads the network, a backend or a
real host tree.
"""

from __future__ import annotations

import pathlib

import yaml

PREFIX = {"goal": "goal", "functional-requirement": "fr", "use-case": "uc"}


def write_record(
    root: pathlib.Path,
    record_id: str,
    frontmatter: dict,
    body: str,
    *,
    subdirectory: str = "",
) -> pathlib.Path:
    """One record file: the frontmatter dumped in key order, then the body. A caller that wants a
    field absent leaves it out of `frontmatter`; one that wants a malformed file writes it by hand."""
    directory = root / subdirectory
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{record_id}.md"
    dumped = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True)
    path.write_text(f"---\n{dumped}---\n{body}\n", encoding="utf-8")
    return path


def node_frontmatter(record_id: str, node_type: str, **fields) -> dict:
    """The smallest sound frontmatter of a node of `node_type`; `fields` override or extend it, and
    a field whose value is None is left out, which is how a test makes one missing."""
    frontmatter: dict = {
        "id": record_id,
        "type": node_type,
        "title": f"Title of {record_id}",
        "sources": ["owner brief"],
    }
    if node_type == "goal":
        # A goal without evaluators is a red check (`goal-without-evaluators`), so the smallest
        # sound goal has one; a test that wants it missing passes `verification=None`.
        frontmatter["verification"] = [{"judge": f"An agent finds that {record_id} holds."}]
    else:
        frontmatter["mechanism"] = "pending"
    frontmatter.update(fields)
    return {key: value for key, value in frontmatter.items() if value is not None}


def write_node(
    root: pathlib.Path,
    record_id: str,
    node_type: str,
    *,
    body: str | None = None,
    subdirectory: str = "",
    **fields,
) -> pathlib.Path:
    text = f"Description of {record_id}." if body is None else body
    return write_record(
        root,
        record_id,
        node_frontmatter(record_id, node_type, **fields),
        text,
        subdirectory=subdirectory,
    )


def decision_frontmatter(record_id: str, **fields) -> dict:
    frontmatter: dict = {
        "id": record_id,
        "type": "decision",
        "title": f"Title of {record_id}",
        "state": "in-force",
        "decided": "2026-10-04",
        "sources": ["owner brief"],
        "premises": [f"Premise of {record_id}"],
        "rejected_alternatives": [
            {"option": "the other way", "reason": "it is worse", "basis": "stated"}
        ],
        "review_triggers": [f"Trigger of {record_id}"],
    }
    frontmatter.update(fields)
    return {key: value for key, value in frontmatter.items() if value is not None}


def write_decision(
    root: pathlib.Path,
    record_id: str,
    *,
    body: str | None = None,
    subdirectory: str = "",
    **fields,
) -> pathlib.Path:
    text = f"Statement of {record_id}." if body is None else body
    return write_record(
        root, record_id, decision_frontmatter(record_id, **fields), text, subdirectory=subdirectory
    )


def write_sound_tree(root: pathlib.Path) -> dict[str, pathlib.Path]:
    """A goal, a requirement, a use case and one decision on the goal: the smallest tree with every
    kind of edge, and no defect. Returned by id."""
    return {
        "goal-notes": write_node(root, "goal-notes", "goal", decisions=["dec-local-first"]),
        "fr-offline": write_node(root, "fr-offline", "functional-requirement", parent="goal-notes"),
        "uc-edit": write_node(
            root,
            "uc-edit",
            "use-case",
            parent="fr-offline",
            verification=[{"command": "pytest tests/test_edit.py -q", "expects": "it persists"}],
        ),
        "dec-local-first": write_decision(root, "dec-local-first"),
    }


def experiment_entry(
    outcome: str = "feasible", *, kind: str = "spike", question: str = "q", **fields
) -> dict:
    """One `experiments` entry; a closed one has a finding, an `open` one has not yet."""
    entry = {"kind": kind, "question": question, "outcome": outcome, "date": "2026-10-04"}
    if outcome != "open":
        entry["finding"] = "f"
    return {**entry, **fields}


def write_unresolvable_node(root: pathlib.Path, record_id: str, *, parent: str) -> pathlib.Path:
    """A use case whose pending mechanism an experiment found infeasible: what `compile` escalates."""
    return write_node(
        root,
        record_id,
        "use-case",
        parent=parent,
        experiments=[experiment_entry("infeasible")],
    )
