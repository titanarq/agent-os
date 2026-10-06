"""The slice (`agent_os.tree.slicing`): a node, its ancestors, the decisions in force on that chain,
and nothing else -- and a size bounded by the chain, not by the tree.

Pure filesystem under `tmp_path`.
"""

from __future__ import annotations

import json
import pathlib

import pytest
from tree_helpers import write_decision, write_node, write_sound_tree

from agent_os.tree.loader import load_tree
from agent_os.tree.slicing import (
    SliceError,
    build_slice,
    render_slice_json,
    render_slice_markdown,
)


def markdown(root: pathlib.Path, node_id: str) -> str:
    return render_slice_markdown(build_slice(load_tree(root), node_id))


def test_a_slice_holds_the_node_its_ancestors_and_the_decisions_on_the_chain(tmp_path):
    write_sound_tree(tmp_path)
    text = markdown(tmp_path, "uc-edit")
    assert "## Node `uc-edit`" in text
    assert "Description of uc-edit." in text
    assert "`pytest tests/test_edit.py -q` -- it persists" in text
    ancestors = text.split("## Ancestors")[1].split("## Decisions in force")[0]
    assert ancestors.index("`fr-offline`") < ancestors.index("`goal-notes`")
    assert "Description of goal-notes." in ancestors
    decisions = text.split("## Decisions in force")[1]
    assert "`dec-local-first`" in decisions
    assert "binds this node through: `goal-notes`" in decisions
    assert "- standing: in force" in decisions


def test_the_slice_carries_every_sources_list_on_the_chain(tmp_path):
    write_sound_tree(tmp_path)
    write_node(
        tmp_path,
        "goal-notes",
        "goal",
        decisions=["dec-local-first"],
        sources=["goal source from the owner"],
    )
    write_node(
        tmp_path,
        "uc-edit",
        "use-case",
        parent="fr-offline",
        sources=["use case source A", "use case source B"],
    )
    text = markdown(tmp_path, "uc-edit")
    for source in ("goal source from the owner", "use case source A", "use case source B"):
        assert f"- {source}" in text


def write_tree_with_acceptance_above(root: pathlib.Path) -> None:
    """The sound tree, but the goal and the requirement each carry the evaluators of their subtree."""
    write_sound_tree(root)
    write_node(
        root,
        "goal-notes",
        "goal",
        decisions=["dec-local-first"],
        verification=[
            {"command": "scripts/check_journey.sh", "expects": "the whole journey holds"}
        ],
    )
    write_node(
        root,
        "fr-offline",
        "functional-requirement",
        parent="goal-notes",
        verification=[{"command": "pytest tests/test_offline.py -q"}],
    )


def test_the_slice_shows_the_acceptance_of_every_ancestor_labelled_as_to_serve_and_not_break(
    tmp_path,
):
    write_tree_with_acceptance_above(tmp_path)
    ancestors = markdown(tmp_path, "uc-edit").split("## Ancestors")[1].split("## Decisions")[0]
    requirement, goal = ancestors.split("### `goal-notes`")
    assert "`pytest tests/test_offline.py -q`" in requirement
    assert "`scripts/check_journey.sh` -- the whole journey holds" in goal
    for block in (requirement, goal):
        assert "serves and must not break" in block
    # The node's own verification stays under its own heading, not among the ancestors'.
    assert "`pytest tests/test_edit.py -q` -- it persists" not in ancestors


def test_an_ancestor_with_no_verification_adds_no_acceptance_block(tmp_path):
    # The goal always carries evaluators (the doctor sees to it), the requirement here has none.
    write_sound_tree(tmp_path)
    ancestors = markdown(tmp_path, "uc-edit").split("## Ancestors")[1].split("## Decisions")[0]
    requirement, goal = ancestors.split("### `goal-notes`")
    assert "must not break" not in requirement
    assert "must not break" in goal


def test_a_goals_own_slice_shows_its_own_verification_under_the_node(tmp_path):
    write_tree_with_acceptance_above(tmp_path)
    own = markdown(tmp_path, "goal-notes").split("## Ancestors")[0]
    assert "### Verification" in own
    assert "`scripts/check_journey.sh` -- the whole journey holds" in own


def test_a_goal_always_shows_its_evaluators_in_its_own_slice(tmp_path):
    write_sound_tree(tmp_path)
    own = markdown(tmp_path, "goal-notes").split("## Ancestors")[0]
    assert "### Verification" in own
    assert "- judged by an agent: An agent finds that goal-notes holds." in own


def test_a_slice_under_a_goal_without_evaluators_is_refused_with_the_doctors_line(tmp_path):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "goal-notes", "goal", decisions=["dec-local-first"], verification=None)
    with pytest.raises(SliceError) as raised:
        build_slice(load_tree(tmp_path), "uc-edit")
    assert [defect.code for defect in raised.value.defects] == ["goal-without-evaluators"]


def write_tree_with_judged_criteria(root: pathlib.Path) -> None:
    """The sound tree where the use case, the requirement and the goal each carry a criterion an
    agent judges, and the use case a command besides."""
    write_sound_tree(root)
    write_node(
        root,
        "goal-notes",
        "goal",
        decisions=["dec-local-first"],
        verification=[
            {"judge": "The owner finds the notes app is the one they asked for."},
            {"command": "scripts/check_journey.sh"},
        ],
    )
    write_node(
        root,
        "fr-offline",
        "functional-requirement",
        parent="goal-notes",
        verification=[{"judge": "Nothing a person wrote is lost when the network is gone."}],
    )
    write_node(
        root,
        "uc-edit",
        "use-case",
        parent="fr-offline",
        verification=[
            {"command": "pytest tests/test_edit.py -q", "expects": "it persists"},
            {"judge": "Editing a note reads as one step to the person doing it."},
        ],
    )


def test_a_judged_criterion_is_rendered_and_labelled_for_the_node_and_for_every_ancestor(tmp_path):
    write_tree_with_judged_criteria(tmp_path)
    text = markdown(tmp_path, "uc-edit")
    own = text.split("## Ancestors")[0]
    assert "- `pytest tests/test_edit.py -q` -- it persists" in own
    assert "- judged by an agent: Editing a note reads as one step to the person doing it." in own
    ancestors = text.split("## Ancestors")[1].split("## Decisions")[0]
    requirement, goal = ancestors.split("### `goal-notes`")
    assert (
        "- judged by an agent: Nothing a person wrote is lost when the network is gone."
        in requirement
    )
    assert "- judged by an agent: The owner finds the notes app is the one they asked for." in goal
    assert "- `scripts/check_journey.sh`" in goal
    for block in (requirement, goal):
        assert "serves and must not break" in block
    # Still the chain only: the node's own judged criterion is not repeated among the ancestors'.
    assert "reads as one step" not in ancestors


def test_a_judged_criterion_over_several_lines_is_one_bullet_that_cannot_open_a_section(tmp_path):
    write_sound_tree(tmp_path)
    write_node(
        tmp_path,
        "uc-edit",
        "use-case",
        parent="fr-offline",
        verification=[
            {
                "judge": (
                    "Editing a note is one step.\n\n## Context\nIt keeps what was typed.\n"
                    "Blocked by #12"
                )
            }
        ],
    )
    own = markdown(tmp_path, "uc-edit").split("## Ancestors")[0]
    assert (
        "- judged by an agent: Editing a note is one step. ## Context It keeps what was typed. "
        "Blocked by #12\n"
    ) in own


def test_the_json_slice_labels_a_judged_criterion_for_the_node_and_for_every_ancestor(tmp_path):
    write_tree_with_judged_criteria(tmp_path)
    data = json.loads(render_slice_json(build_slice(load_tree(tmp_path), "uc-edit")))
    assert data["node"]["verification"] == [
        {"kind": "command", "command": "pytest tests/test_edit.py -q", "expects": "it persists"},
        {
            "kind": "judge",
            "judge": "Editing a note reads as one step to the person doing it.",
            "label": "judged by an agent",
        },
    ]
    by_id = {ancestor["id"]: ancestor for ancestor in data["ancestors"]}
    assert by_id["fr-offline"]["verification"] == [
        {
            "kind": "judge",
            "judge": "Nothing a person wrote is lost when the network is gone.",
            "label": "judged by an agent",
        }
    ]
    assert by_id["goal-notes"]["verification"] == [
        {
            "kind": "judge",
            "judge": "The owner finds the notes app is the one they asked for.",
            "label": "judged by an agent",
        },
        {"kind": "command", "command": "scripts/check_journey.sh", "expects": None},
    ]


def test_a_decision_under_review_is_in_the_slice_and_labelled_as_still_obeyed(tmp_path):
    write_sound_tree(tmp_path)
    write_decision(tmp_path, "dec-local-first", state="under-review")
    text = markdown(tmp_path, "uc-edit")
    assert "UNDER REVIEW -- still obeyed while it is challenged" in text


def test_an_in_force_decision_carries_no_review_label(tmp_path):
    write_sound_tree(tmp_path)
    assert "UNDER REVIEW" not in markdown(tmp_path, "uc-edit")


def test_the_decision_in_the_slice_shows_what_stops_a_worker_relitigating_it(tmp_path):
    write_sound_tree(tmp_path)
    write_decision(
        tmp_path,
        "dec-local-first",
        friction=[{"date": "2026-10-05", "summary": "it hurt"}] * 3,
        rejected_alternatives=[
            {"option": "server first", "reason": "breaks offline", "basis": "stated"},
            {"option": "peer to peer", "reason": "no reason on record", "basis": "implied"},
        ],
        review_triggers=["a second device", "sync becomes the bottleneck"],
    )
    text = markdown(tmp_path, "uc-edit")
    assert "Premises:\n- Premise of dec-local-first" in text
    assert "- server first -- breaks offline\n" in text
    assert "- peer to peer -- no reason on record (implied, not argued at approval)" in text
    assert "- a second device\n- sync becomes the bottleneck" in text
    assert "Friction entries logged against it: 3" in text
    # The friction ENTRIES are not in the slice, only their count: they grow without bound.
    assert "it hurt" not in text


def test_a_decision_on_the_node_and_on_an_ancestor_appears_once_at_the_nearest(tmp_path):
    write_sound_tree(tmp_path)
    write_node(
        tmp_path,
        "uc-edit",
        "use-case",
        parent="fr-offline",
        decisions=["dec-local-first"],
        verification=[{"command": "true"}],
    )
    text = markdown(tmp_path, "uc-edit")
    assert text.count("### `dec-local-first`") == 1
    assert "binds this node through: `uc-edit`" in text


def test_a_decision_on_the_requirement_binds_its_use_cases(tmp_path):
    write_sound_tree(tmp_path)
    write_decision(tmp_path, "dec-on-requirement")
    write_node(
        tmp_path,
        "fr-offline",
        "functional-requirement",
        parent="goal-notes",
        decisions=["dec-on-requirement"],
    )
    text = markdown(tmp_path, "uc-edit")
    assert "binds this node through: `fr-offline`" in text


def test_a_goal_has_no_ancestors(tmp_path):
    write_sound_tree(tmp_path)
    text = markdown(tmp_path, "goal-notes")
    assert "## Ancestors\n\nnone" in text


def test_a_node_with_no_decision_in_force_says_so(tmp_path):
    write_node(tmp_path, "goal-bare", "goal")
    assert "## Decisions in force\n\nnone" in markdown(tmp_path, "goal-bare")


# --------------------------------------------------------------------------------------------
# What a slice is not
# --------------------------------------------------------------------------------------------


def _add_the_rest_of_a_large_tree(root: pathlib.Path, width: int) -> None:
    """Everything a slice of `uc-edit` must NOT contain, `width` times over: siblings, cousins,
    descendants, other goals, and decisions nobody on the chain points at."""
    for index in range(width):
        write_node(
            root,
            f"uc-sibling-{index}",
            "use-case",
            parent="fr-offline",
            body=f"SIBLING TEXT {index} " * 40,
            decisions=[f"dec-elsewhere-{index}"],
            verification=[{"command": f"SIBLING VERIFICATION {index}"}],
        )
        write_node(
            root,
            f"fr-cousin-{index}",
            "functional-requirement",
            parent="goal-notes",
            body=f"COUSIN TEXT {index} " * 40,
            verification=[{"command": f"COUSIN VERIFICATION {index}"}],
        )
        write_node(
            root,
            f"goal-other-{index}",
            "goal",
            body=f"OTHER GOAL TEXT {index} " * 40,
            verification=[{"command": f"OTHER GOAL VERIFICATION {index}"}],
        )
        write_decision(root, f"dec-elsewhere-{index}", body=f"ELSEWHERE TEXT {index} " * 40)
    write_node(
        root,
        "uc-edit-child",
        "use-case",
        parent="uc-edit",
        body="DESCENDANT TEXT " * 40,
        verification=[{"command": "DESCENDANT VERIFICATION"}],
    )


def test_a_slice_excludes_siblings_cousins_descendants_and_unrelated_decisions(tmp_path):
    write_sound_tree(tmp_path)
    _add_the_rest_of_a_large_tree(tmp_path, 5)
    text = markdown(tmp_path, "uc-edit")
    for foreign in ("uc-sibling", "fr-cousin", "goal-other", "dec-elsewhere", "uc-edit-child"):
        assert foreign not in text
    for foreign_text in (
        "SIBLING TEXT",
        "COUSIN TEXT",
        "OTHER GOAL TEXT",
        "ELSEWHERE",
        "DESCENDANT",
        "VERIFICATION",
    ):
        assert foreign_text not in text


@pytest.mark.parametrize("with_acceptance_above", [False, True])
@pytest.mark.parametrize("renderer", ["markdown", "json"])
def test_a_slice_is_bounded_by_its_chain_and_not_by_the_size_of_the_tree(
    tmp_path, renderer, with_acceptance_above
):
    small = tmp_path / "small"
    large = tmp_path / "large"
    small.mkdir()
    large.mkdir()
    # The evaluators above are part of the chain, so they are in both slices and the same.
    write_tree = write_tree_with_acceptance_above if with_acceptance_above else write_sound_tree
    write_tree(small)
    write_tree(large)
    _add_the_rest_of_a_large_tree(large, 300)

    def render(root: pathlib.Path) -> str:
        cut = build_slice(load_tree(root), "uc-edit")
        return render_slice_markdown(cut) if renderer == "markdown" else render_slice_json(cut)

    assert len(load_tree(large).nodes) > 900
    # Not "about the same size": the very same bytes.
    assert render(large) == render(small)


def test_the_slice_is_the_same_whatever_order_the_files_were_written_in(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    write_decision(first, "dec-b")
    write_decision(first, "dec-a")
    write_node(first, "goal-notes", "goal", decisions=["dec-b", "dec-a"])
    write_node(first, "fr-offline", "functional-requirement", parent="goal-notes")
    write_node(first, "uc-edit", "use-case", parent="fr-offline")
    # The same tree, files written the other way round, decisions listed in the other order.
    write_node(second, "uc-edit", "use-case", parent="fr-offline")
    write_node(second, "fr-offline", "functional-requirement", parent="goal-notes")
    write_node(second, "goal-notes", "goal", decisions=["dec-a", "dec-b"])
    write_decision(second, "dec-a")
    write_decision(second, "dec-b")
    assert markdown(first, "uc-edit") == markdown(second, "uc-edit")
    assert markdown(first, "uc-edit").index("`dec-a`") < markdown(first, "uc-edit").index("`dec-b`")


def test_the_same_tree_gives_the_same_slice_twice(tmp_path):
    write_sound_tree(tmp_path)
    assert markdown(tmp_path, "uc-edit") == markdown(tmp_path, "uc-edit")


# --------------------------------------------------------------------------------------------
# When the slice cannot be cut
# --------------------------------------------------------------------------------------------


def test_an_unknown_node_is_an_error_naming_it(tmp_path):
    write_sound_tree(tmp_path)
    with pytest.raises(SliceError, match="no node 'uc-ghost'"):
        build_slice(load_tree(tmp_path), "uc-ghost")


def test_a_decision_is_not_something_a_slice_is_cut_around(tmp_path):
    write_sound_tree(tmp_path)
    with pytest.raises(SliceError, match="is a decision, not a node"):
        build_slice(load_tree(tmp_path), "dec-local-first")


def test_a_node_that_failed_to_load_is_refused_with_a_pointer_to_the_doctor(tmp_path):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "uc-broken", "use-case", parent="fr-offline", sources=None)
    with pytest.raises(SliceError, match="cannot be loaded"):
        build_slice(load_tree(tmp_path), "uc-broken")


def test_a_slice_over_a_dangling_parent_is_refused(tmp_path):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "uc-orphan", "use-case", parent="fr-gone")
    with pytest.raises(SliceError, match="dangling-parent"):
        build_slice(load_tree(tmp_path), "uc-orphan")


def test_a_slice_over_a_superseded_decision_is_refused_and_says_what_the_doctor_says(tmp_path):
    write_sound_tree(tmp_path)
    write_decision(tmp_path, "dec-local-first", state="superseded", superseded_by="dec-new")
    write_decision(tmp_path, "dec-new")
    with pytest.raises(SliceError) as raised:
        build_slice(load_tree(tmp_path), "uc-edit")
    assert "superseded-decision-in-use" in str(raised.value)


def test_a_slice_made_of_a_file_that_fails_the_doctor_is_refused_with_its_defects(tmp_path):
    write_sound_tree(tmp_path)
    write_node(
        tmp_path,
        "uc-edit",
        "use-case",
        parent="fr-offline",
        state="hardened",
        verification=[{"command": "true"}],
    )
    with pytest.raises(SliceError) as raised:
        build_slice(load_tree(tmp_path), "uc-edit")
    assert [defect.code for defect in raised.value.defects] == ["hardened-needs-implementation"]


def test_a_defect_in_another_branch_does_not_stop_a_slice(tmp_path):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "uc-elsewhere", "use-case")  # parent-missing, not on uc-edit's chain
    (tmp_path / "stray.txt").write_text("x")
    assert "## Node `uc-edit`" in markdown(tmp_path, "uc-edit")


# --------------------------------------------------------------------------------------------
# JSON
# --------------------------------------------------------------------------------------------


def test_the_json_slice_has_the_same_content_as_structured_data(tmp_path):
    write_sound_tree(tmp_path)
    write_decision(tmp_path, "dec-local-first", state="under-review")
    data = json.loads(render_slice_json(build_slice(load_tree(tmp_path), "uc-edit")))
    assert set(data) == {"node", "ancestors", "decisions"}
    assert data["node"]["id"] == "uc-edit"
    assert data["node"]["file"] == "uc-edit.md"
    assert data["node"]["verification"] == [
        {"kind": "command", "command": "pytest tests/test_edit.py -q", "expects": "it persists"}
    ]
    assert [ancestor["id"] for ancestor in data["ancestors"]] == ["fr-offline", "goal-notes"]
    assert [ancestor["verification"] for ancestor in data["ancestors"]] == [
        [],
        [
            {
                "kind": "judge",
                "judge": "An agent finds that goal-notes holds.",
                "label": "judged by an agent",
            }
        ],
    ]
    (decision,) = data["decisions"]
    assert decision["id"] == "dec-local-first"
    assert decision["state"] == "under-review"
    assert decision["attached_to"] == "goal-notes"
    assert decision["friction_count"] == 0
    assert "friction" not in decision


def test_the_json_slice_carries_the_verification_of_each_ancestor(tmp_path):
    write_tree_with_acceptance_above(tmp_path)
    data = json.loads(render_slice_json(build_slice(load_tree(tmp_path), "uc-edit")))
    by_id = {ancestor["id"]: ancestor for ancestor in data["ancestors"]}
    assert by_id["fr-offline"]["verification"] == [
        {"kind": "command", "command": "pytest tests/test_offline.py -q", "expects": None}
    ]
    assert by_id["goal-notes"]["verification"] == [
        {
            "kind": "command",
            "command": "scripts/check_journey.sh",
            "expects": "the whole journey holds",
        }
    ]
    # Still the chain only: the node's own verification is under `node`, not repeated above.
    assert "pytest tests/test_edit.py -q" not in json.dumps(data["ancestors"])
