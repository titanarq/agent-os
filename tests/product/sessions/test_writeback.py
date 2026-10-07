"""An answer written into its node, a reclaim into a new question, and the tree staying valid."""

from __future__ import annotations

import datetime

import pytest
from sessions_support import what_question, write_node

from agent_os.product.sessions.writeback import (
    WritebackError,
    answer_question,
    raise_reclaimed_question,
)
from agent_os.product.tree.checks import check_tree
from agent_os.product.tree.loader import load_tree

QUESTION = "Sort order of notes?"


def sound_tree(tmp_path):
    write_node(tmp_path, "goal-a", "goal")
    write_node(
        tmp_path,
        "fr-a",
        "functional-requirement",
        parent="goal-a",
        experiments=[what_question(QUESTION, "newest first")],
    )
    return load_tree(tmp_path)


def test_an_answer_makes_the_question_answered_with_the_owners_words_as_finding(tmp_path):
    tree = sound_tree(tmp_path)
    answer_question(tree, "fr-a", QUESTION, "oldest first")
    experiment = load_tree(tmp_path).nodes["fr-a"].experiments[0]
    assert (experiment.outcome, experiment.finding) == ("answered", "oldest first")
    assert experiment.default_answer == "newest first"
    assert check_tree(load_tree(tmp_path)) == []


def test_the_markdown_body_is_kept_byte_for_byte(tmp_path):
    tree = sound_tree(tmp_path)
    before = tree.paths["fr-a"].read_text().split("---\n", 2)[2]
    answer_question(tree, "fr-a", QUESTION, "oldest first")
    assert tree.paths["fr-a"].read_text().split("---\n", 2)[2] == before


def test_answering_a_question_that_is_not_open_is_refused_and_writes_nothing(tmp_path):
    tree = sound_tree(tmp_path)
    answer_question(tree, "fr-a", QUESTION, "oldest first")
    text = tree.paths["fr-a"].read_text()
    with pytest.raises(WritebackError, match="no open question"):
        answer_question(tree, "fr-a", QUESTION, "again")
    assert tree.paths["fr-a"].read_text() == text


def test_an_unknown_node_is_refused(tmp_path):
    with pytest.raises(WritebackError, match="no node"):
        answer_question(sound_tree(tmp_path), "fr-zzz", QUESTION, "x")


def test_a_reclaim_adds_an_open_what_question_whose_default_is_the_decision(tmp_path):
    tree = sound_tree(tmp_path)
    raise_reclaimed_question(tree, "fr-a", "weekly view", raised_on=datetime.date(2026, 10, 7))
    reloaded = load_tree(tmp_path)
    added = reloaded.nodes["fr-a"].experiments[1]
    assert added.is_open_what_question and added.default_answer == "weekly view"
    assert reloaded.nodes["fr-a"].has_open_what_question
    assert check_tree(reloaded) == []
    with pytest.raises(WritebackError, match="already"):
        raise_reclaimed_question(
            reloaded, "fr-a", "weekly view", raised_on=datetime.date(2026, 10, 7)
        )
