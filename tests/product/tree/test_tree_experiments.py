"""Experiments, challenges and the `implemented` state of a node, and what makes a node not
hardenable (`agent_os.product.tree.hardening`). Pure filesystem under `tmp_path`.
"""

from __future__ import annotations

import json
import pathlib

import pytest
from tree_helpers import write_node, write_sound_tree

from agent_os.product.tree.checks import check_tree
from agent_os.product.tree.hardening import hardening_blockers, is_hardenable
from agent_os.product.tree.loader import load_tree
from agent_os.product.tree.slicing import build_slice, render_slice_json, render_slice_markdown

DATE = "2026-10-07"


def experiment(kind="spike", outcome="feasible", **fields) -> dict:
    entry = {"kind": kind, "question": "does it work", "outcome": outcome, "date": DATE}
    if outcome != "open":
        entry["finding"] = "it does"
    entry.update(fields)
    return entry


def tree_with(root: pathlib.Path, **fields):
    write_sound_tree(root)
    write_node(root, "uc-edit", "use-case", parent="fr-offline", **fields)
    return load_tree(root)


def codes(tree) -> list[str]:
    return [defect.code for defect in check_tree(tree)]


def messages(tree) -> list[str]:
    return [defect.message for defect in check_tree(tree)]


@pytest.mark.parametrize("kind", ["spike", "demand-probe", "lookup"])
@pytest.mark.parametrize("outcome", ["open", "feasible", "infeasible", "inconclusive"])
def test_every_kind_of_experiment_may_have_every_outcome(tmp_path, kind, outcome):
    assert codes(tree_with(tmp_path, experiments=[experiment(kind, outcome)])) == []


def test_an_implemented_node_is_sound(tmp_path):
    assert codes(tree_with(tmp_path, state="implemented")) == []


def test_the_old_spikes_field_is_gone(tmp_path):
    tree = tree_with(tmp_path, spikes=[experiment()])
    assert codes(tree) == ["schema"]
    assert "spikes" in messages(tree)[0]


def test_an_open_experiment_needs_no_finding_but_a_closed_one_does(tmp_path):
    assert codes(tree_with(tmp_path, experiments=[experiment(outcome="open")])) == []
    closed = experiment()
    del closed["finding"]
    assert codes(tree_with(tmp_path, experiments=[closed])) == ["schema"]


def test_an_unknown_experiment_kind_is_a_schema_error(tmp_path):
    assert codes(tree_with(tmp_path, experiments=[experiment(kind="hunch")])) == ["schema"]


def test_a_question_carries_its_scope_and_a_what_question_its_default_answer(tmp_path):
    how = experiment("question", "open", scope="how")
    what = experiment("question", "open", scope="what", default_answer="keep the current layout")
    assert codes(tree_with(tmp_path, experiments=[how, what])) == []
    no_scope = experiment("question", "open")
    assert codes(tree_with(tmp_path, experiments=[no_scope])) == ["schema"]
    no_default = experiment("question", "open", scope="what")
    assert codes(tree_with(tmp_path, experiments=[no_default])) == ["schema"]


@pytest.mark.parametrize("extra", [{"scope": "what"}, {"default_answer": "x"}])
def test_scope_and_default_answer_belong_to_a_question_only(tmp_path, extra):
    assert codes(tree_with(tmp_path, experiments=[experiment("spike", **extra)])) == ["schema"]


def test_an_answered_question_is_closed_with_its_answer(tmp_path):
    answered = experiment(
        "question", "answered", scope="what", default_answer="d", finding="the owner chose d"
    )
    assert codes(tree_with(tmp_path, experiments=[answered])) == []
    assert codes(tree_with(tmp_path, experiments=[experiment("spike", "answered")])) == ["schema"]


def test_a_challenge_has_one_of_three_reasons(tmp_path):
    for reason in ("no-solution", "no-verification", "over-cost"):
        assert codes(tree_with(tmp_path, challenge={"reason": reason})) == []
    assert codes(tree_with(tmp_path, challenge={"reason": "too-hard"})) == ["schema"]
    assert codes(tree_with(tmp_path, challenge={})) == ["schema"]


def test_a_challenge_may_carry_an_explanation(tmp_path):
    tree = tree_with(tmp_path, challenge={"reason": "over-cost", "explanation": "ten times budget"})
    assert codes(tree) == []
    assert tree.nodes["uc-edit"].challenge.explanation == "ten times budget"


def test_a_goal_may_be_challenged(tmp_path):
    write_sound_tree(tmp_path)
    write_node(
        tmp_path,
        "goal-notes",
        "goal",
        decisions=["dec-local-first"],
        challenge={"reason": "no-solution"},
    )
    assert codes(load_tree(tmp_path)) == []


# -------------------------------------------------------------------- not hardenable


def test_a_node_without_doubts_is_hardenable(tmp_path):
    tree = tree_with(tmp_path)
    assert is_hardenable(tree, "uc-edit")
    assert hardening_blockers(tree, "uc-edit") == []


def test_an_open_what_question_makes_a_node_not_hardenable(tmp_path):
    question = experiment("question", "open", scope="what", default_answer="d")
    tree = tree_with(tmp_path, experiments=[question])
    assert tree.nodes["uc-edit"].has_open_what_question
    assert not is_hardenable(tree, "uc-edit")
    (blocker,) = hardening_blockers(tree, "uc-edit")
    assert blocker.node_id == "uc-edit" and blocker.reason == "open-what-question"


def test_an_open_how_question_or_a_closed_what_question_does_not_block(tmp_path):
    how = experiment("question", "open", scope="how")
    closed = experiment("question", "answered", scope="what", default_answer="d")
    tree = tree_with(tmp_path, experiments=[how, closed])
    assert is_hardenable(tree, "uc-edit")


def test_a_challenge_on_the_node_blocks_hardening(tmp_path):
    tree = tree_with(tmp_path, challenge={"reason": "no-verification"})
    (blocker,) = hardening_blockers(tree, "uc-edit")
    assert (blocker.node_id, blocker.reason) == ("uc-edit", "challenge:no-verification")


def test_a_challenge_on_what_it_depends_on_blocks_hardening_transitively(tmp_path):
    write_sound_tree(tmp_path)
    write_node(
        tmp_path, "uc-base", "use-case", parent="fr-offline", challenge={"reason": "over-cost"}
    )
    write_node(tmp_path, "uc-middle", "use-case", parent="fr-offline", depends_on=["uc-base"])
    write_node(tmp_path, "uc-edit", "use-case", parent="fr-offline", depends_on=["uc-middle"])
    tree = load_tree(tmp_path)
    assert not is_hardenable(tree, "uc-edit")
    assert [b.node_id for b in hardening_blockers(tree, "uc-edit")] == ["uc-base"]
    assert is_hardenable(tree, "uc-base") is False
    assert is_hardenable(tree, "fr-offline")


def test_an_open_what_question_on_a_dependency_blocks_hardening(tmp_path):
    write_sound_tree(tmp_path)
    question = experiment("question", "open", scope="what", default_answer="d")
    write_node(tmp_path, "uc-base", "use-case", parent="fr-offline", experiments=[question])
    write_node(tmp_path, "uc-edit", "use-case", parent="fr-offline", depends_on=["uc-base"])
    assert not is_hardenable(load_tree(tmp_path), "uc-edit")


def test_blockers_terminate_on_a_dependency_cycle(tmp_path):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "uc-a", "use-case", parent="fr-offline", depends_on=["uc-b"])
    write_node(tmp_path, "uc-b", "use-case", parent="fr-offline", depends_on=["uc-a"])
    assert is_hardenable(load_tree(tmp_path), "uc-a")


# ------------------------------------------------------------------------ the slice


def test_the_slice_shows_state_experiments_challenge_and_dependencies(tmp_path):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "uc-base", "use-case", parent="fr-offline")
    question = experiment("question", "open", scope="what", default_answer="keep it simple")
    write_node(
        tmp_path,
        "uc-edit",
        "use-case",
        parent="fr-offline",
        state="implemented",
        depends_on=["uc-base"],
        challenge={"reason": "over-cost", "explanation": "ten times budget"},
        experiments=[experiment("lookup"), question],
    )
    tree = load_tree(tmp_path)
    text = render_slice_markdown(build_slice(tree, "uc-edit"))
    assert "- state: implemented" in text
    assert "- depends on: `uc-base`" in text
    assert "Challenge" in text and "over-cost" in text and "ten times budget" in text
    assert "lookup, feasible" in text
    assert "question (what), open" in text and "default answer: keep it simple" in text
    assert "- hardenable: no" in text
    data = json.loads(render_slice_json(build_slice(tree, "uc-edit")))["node"]
    assert data["depends_on"] == ["uc-base"]
    assert data["challenge"]["reason"] == "over-cost"
    assert data["experiments"][1]["scope"] == "what"
    assert data["hardenable"] is False


def test_a_plain_slice_says_it_is_hardenable_and_lists_no_dependency(tmp_path):
    tree = tree_with(tmp_path)
    text = render_slice_markdown(build_slice(tree, "uc-edit"))
    assert "- hardenable: yes" in text
    assert "depends on" not in text and "Challenge" not in text
