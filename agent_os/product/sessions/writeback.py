"""Writing a session's result into the tree: an answer into its node, a reclaim into a new question,
an owner's acceptance into the node it accepted.

All three edit the node file's frontmatter and nothing else (the Markdown body is kept byte for byte),
then check that the result is still a valid node: a write-back that corrupted a node must fail
here, not in the next doctor run. The frontmatter is re-dumped, so YAML comments and quoting style
inside it are not preserved.

An answer is written by a pull request, never straight onto main; this module only produces the
edit. That pull request touches the what and is merged on the owner's word, which the answer is
(`docs/tree/dec-a-change-to-the-what-is-merged-only-on-the-owners-word.md`).
"""

from __future__ import annotations

import datetime
import pathlib

import yaml

from agent_os.product.tree.loader import Tree, split_frontmatter
from agent_os.product.tree.models import Node


class WritebackError(ValueError):
    """The edit cannot be made as asked; nothing was written."""


def _load_node_file(tree: Tree, node_id: str) -> tuple[pathlib.Path, dict, str]:
    path = tree.paths.get(node_id)
    if node_id not in tree.nodes or path is None:
        raise WritebackError(f"no node {node_id!r} in the tree")
    parts = split_frontmatter(path.read_text(encoding="utf-8"))
    if parts is None:
        raise WritebackError(f"{path} has no frontmatter block")
    frontmatter_text, body = parts
    return path, yaml.safe_load(frontmatter_text), body


def _write_node_file(path: pathlib.Path, frontmatter: dict, body: str) -> None:
    Node.model_validate({**frontmatter, "description": body.strip() or "-"})
    dumped = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True)
    path.write_text(f"---\n{dumped}---\n{body}", encoding="utf-8")


def answer_question(tree: Tree, node_id: str, question: str, answer: str) -> pathlib.Path:
    """The open question of `what` becomes `answered`, the owner's words -- exactly, so that the
    validator can compare them -- its `finding`."""
    path, frontmatter, body = _load_node_file(tree, node_id)
    for experiment in frontmatter.get("experiments") or []:
        if (
            experiment.get("kind") == "question"
            and experiment.get("scope") == "what"
            and experiment.get("outcome") == "open"
            and experiment.get("question") == question
        ):
            experiment["outcome"] = "answered"
            experiment["finding"] = answer
            _write_node_file(path, frontmatter, body)
            return path
    raise WritebackError(f"{node_id} has no open question of what reading {question!r}")


def raise_reclaimed_question(
    tree: Tree, node_id: str, decision: str, *, raised_on: datetime.date
) -> pathlib.Path:
    """A decision taken without the owner becomes a question of what whose default is that very
    decision, so asking costs nothing if the owner is content with it."""
    path, frontmatter, body = _load_node_file(tree, node_id)
    question = f"Reclaimed from the digest: {decision} -- what should it be?"
    existing = frontmatter.setdefault("experiments", [])
    if any(
        entry.get("question") == question and entry.get("outcome") == "open" for entry in existing
    ):
        raise WritebackError(f"{node_id} already carries that reclaimed question")
    existing.append(
        {
            "kind": "question",
            "question": question,
            "outcome": "open",
            "date": raised_on,
            "scope": "what",
            "default_answer": decision,
        }
    )
    _write_node_file(path, frontmatter, body)
    return path


def record_acceptance(
    tree: Tree, node_id: str, session_id: str, *, accepted_on: datetime.date
) -> pathlib.Path | None:
    """The owner accepted this node in a test session: the node says so, once per session (a second
    ingestion of the same session writes nothing and returns None). Evidence, not a change of the
    what: the node's own words stay as they were."""
    path, frontmatter, body = _load_node_file(tree, node_id)
    acceptances = frontmatter.setdefault("acceptances", [])
    if any(entry.get("session") == session_id for entry in acceptances):
        return None
    acceptances.append({"session": session_id, "date": accepted_on})
    _write_node_file(path, frontmatter, body)
    return path
