"""The tree doctor (`agent_os.tree.checks`): every rule is a named code, and a sound tree has none.

Each case starts from the smallest sound tree (`write_sound_tree`), breaks exactly one thing, and
asserts the doctor reports exactly the expected `(file, code)` pairs -- so a check that fires twice,
or that fires on the wrong file, or that is silent, fails here. Pure filesystem under `tmp_path`.
"""

from __future__ import annotations

import pathlib
import typing

import pytest
from tree_helpers import (
    node_frontmatter,
    write_decision,
    write_node,
    write_record,
    write_sound_tree,
)

from agent_os.tree.checks import CHECKS, check_tree
from agent_os.tree.loader import TreeRootError, load_tree
from agent_os.tree.models import (
    BODY_FIELD_BY_TYPE,
    ID_PREFIX_BY_TYPE,
    NODE_TYPES,
    RECORD_TYPES,
    Node,
)


def found(root: pathlib.Path) -> list[tuple[str, str]]:
    return [(defect.path.name, defect.code) for defect in check_tree(load_tree(root))]


def messages(root: pathlib.Path) -> list[str]:
    return [defect.message for defect in check_tree(load_tree(root))]


def test_a_sound_tree_has_no_defect(tmp_path):
    write_sound_tree(tmp_path)
    assert check_tree(load_tree(tmp_path)) == []


def test_an_empty_root_is_a_valid_fresh_tree(tmp_path):
    assert check_tree(load_tree(tmp_path)) == []


def test_a_missing_root_is_an_error_and_never_an_empty_tree(tmp_path):
    with pytest.raises(TreeRootError, match="is not a directory"):
        load_tree(tmp_path / "not-there")


def test_a_root_that_is_a_file_is_an_error(tmp_path):
    stray = tmp_path / "file.md"
    stray.write_text("x")
    with pytest.raises(TreeRootError):
        load_tree(stray)


def test_the_vocabularies_the_checks_and_the_schema_use_are_one_vocabulary():
    # `Node.type` is a `Literal` the models spell out; the constants the checks read must say the
    # same thing, or a type could pass the schema and miss a prefix or a body field.
    assert typing.get_args(Node.model_fields["type"].annotation) == NODE_TYPES
    assert set(ID_PREFIX_BY_TYPE) == set(RECORD_TYPES) == set(BODY_FIELD_BY_TYPE)


def test_every_code_the_doctor_can_emit_is_listed_in_checks():
    # The loader's four codes and every code of `checks.py`: the list is what the docs table is
    # compared against, so a code missing here would be undocumented.
    assert {"orphan-file", "bad-frontmatter", "schema", "duplicate-id"} <= set(CHECKS)
    assert all(CHECKS[code].strip() for code in CHECKS)


# --------------------------------------------------------------------------------------------
# What is not a record at all
# --------------------------------------------------------------------------------------------


def test_a_file_that_is_not_markdown_is_an_orphan(tmp_path):
    write_sound_tree(tmp_path)
    (tmp_path / "notes.txt").write_text("loose thoughts")
    assert found(tmp_path) == [("notes.txt", "orphan-file")]


def test_a_non_markdown_file_is_an_orphan_even_with_a_perfect_frontmatter(tmp_path):
    write_sound_tree(tmp_path)
    (tmp_path / "uc-sneaky.txt").write_text(
        "---\nid: uc-sneaky\ntype: use-case\n---\nbody\n", encoding="utf-8"
    )
    assert found(tmp_path) == [("uc-sneaky.txt", "orphan-file")]
    assert "not a Markdown file" in messages(tmp_path)[0]


def test_a_markdown_file_without_frontmatter_is_an_orphan(tmp_path):
    write_sound_tree(tmp_path)
    (tmp_path / "stray.md").write_text("# Just a note\n")
    assert found(tmp_path) == [("stray.md", "orphan-file")]


def test_an_unclosed_frontmatter_is_an_orphan(tmp_path):
    write_sound_tree(tmp_path)
    (tmp_path / "stray.md").write_text("---\nid: stray\n")
    assert found(tmp_path) == [("stray.md", "orphan-file")]


def test_a_frontmatter_without_a_type_is_an_orphan(tmp_path):
    write_sound_tree(tmp_path)
    (tmp_path / "stray.md").write_text("---\ntitle: nothing\n---\nbody\n")
    assert found(tmp_path) == [("stray.md", "orphan-file")]


def test_a_type_that_is_neither_node_nor_decision_is_an_orphan(tmp_path):
    write_sound_tree(tmp_path)
    write_record(tmp_path, "epic-big", {"id": "epic-big", "type": "epic"}, "body")
    assert found(tmp_path) == [("epic-big.md", "orphan-file")]
    assert "neither a node nor a decision" in messages(tmp_path)[0]


def test_a_file_in_a_subdirectory_is_found_and_counted(tmp_path):
    write_sound_tree(tmp_path)
    (tmp_path / "deep" / "er").mkdir(parents=True)
    (tmp_path / "deep" / "er" / "stray.csv").write_text("a,b")
    assert found(tmp_path) == [("stray.csv", "orphan-file")]


def test_hidden_files_and_directories_are_not_content(tmp_path):
    write_sound_tree(tmp_path)
    (tmp_path / ".gitkeep").write_text("")
    (tmp_path / ".cache").mkdir()
    (tmp_path / ".cache" / "scratch.txt").write_text("x")
    assert found(tmp_path) == []


def test_malformed_yaml_is_a_bad_frontmatter(tmp_path):
    write_sound_tree(tmp_path)
    (tmp_path / "uc-broken.md").write_text("---\nid: [unclosed\n---\nbody\n")
    assert found(tmp_path) == [("uc-broken.md", "bad-frontmatter")]


def test_a_duplicate_key_is_a_bad_frontmatter_and_not_a_silent_last_one_wins(tmp_path):
    write_sound_tree(tmp_path)
    write_decision(tmp_path, "dec-twice")
    text = (tmp_path / "dec-twice.md").read_text()
    (tmp_path / "dec-twice.md").write_text(text.replace("\n---\n", "\npremises: [again]\n---\n", 1))
    assert found(tmp_path) == [("dec-twice.md", "bad-frontmatter")]
    assert "duplicate key 'premises'" in messages(tmp_path)[0]


def test_an_impossible_bare_date_is_a_bad_frontmatter_and_not_a_crash(tmp_path):
    # YAML itself raises ValueError for a bare 2026-13-45, which is not a YAMLError.
    write_sound_tree(tmp_path)
    write_decision(tmp_path, "dec-late")
    text = (tmp_path / "dec-late.md").read_text()
    (tmp_path / "dec-late.md").write_text(text.replace("'2026-10-04'", "2026-13-45"))
    assert found(tmp_path) == [("dec-late.md", "bad-frontmatter")]


def test_an_impossible_quoted_date_is_a_schema_defect_naming_the_field(tmp_path):
    write_sound_tree(tmp_path)
    write_decision(tmp_path, "dec-late", decided="2026-13-45")
    assert found(tmp_path) == [("dec-late.md", "schema")]
    assert messages(tmp_path)[0].startswith("decided: ")


def test_frontmatter_that_is_not_a_mapping_is_a_bad_frontmatter(tmp_path):
    write_sound_tree(tmp_path)
    (tmp_path / "uc-list.md").write_text("---\n- a\n- b\n---\nbody\n")
    assert found(tmp_path) == [("uc-list.md", "bad-frontmatter")]


# --------------------------------------------------------------------------------------------
# Shape: missing, unknown, empty
# --------------------------------------------------------------------------------------------


def test_a_missing_field_is_a_red_check_naming_the_field(tmp_path):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "uc-nosource", "use-case", parent="fr-offline", sources=None)
    assert found(tmp_path) == [("uc-nosource.md", "schema")]
    assert messages(tmp_path) == ["sources: missing field"]


def test_an_unknown_field_is_a_red_check(tmp_path):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "uc-extra", "use-case", parent="fr-offline", colour="red")
    assert found(tmp_path) == [("uc-extra.md", "schema")]
    assert messages(tmp_path) == ["colour: unknown field"]


def test_an_empty_markdown_body_is_a_red_check(tmp_path):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "uc-silent", "use-case", parent="fr-offline", body="   ")
    assert found(tmp_path) == [("uc-silent.md", "schema")]
    assert "the Markdown body is empty" in messages(tmp_path)[0]


def test_a_description_written_in_the_frontmatter_is_refused(tmp_path):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "uc-twice", "use-case", parent="fr-offline", description="here")
    assert found(tmp_path) == [("uc-twice.md", "schema")]
    assert "write it as the Markdown body" in messages(tmp_path)[0]


def test_a_node_needs_at_least_one_source(tmp_path):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "uc-nosource", "use-case", parent="fr-offline", sources=[])
    assert found(tmp_path) == [("uc-nosource.md", "schema")]
    assert messages(tmp_path) == ["sources: must have at least one entry"]


@pytest.mark.parametrize(
    "field", ["premises", "review_triggers", "rejected_alternatives", "sources"]
)
def test_a_decision_without_a_mandatory_list_is_red(tmp_path, field):
    write_sound_tree(tmp_path)
    write_decision(tmp_path, "dec-bare", **{field: None})
    assert found(tmp_path) == [("dec-bare.md", "schema")]
    assert messages(tmp_path) == [f"{field}: missing field"]


@pytest.mark.parametrize("field", ["premises", "review_triggers", "rejected_alternatives"])
def test_a_decision_with_an_empty_mandatory_list_is_red(tmp_path, field):
    write_sound_tree(tmp_path)
    write_decision(tmp_path, "dec-bare", **{field: []})
    assert found(tmp_path) == [("dec-bare.md", "schema")]
    assert messages(tmp_path) == [f"{field}: must have at least one entry"]


def test_an_alternative_must_say_whether_it_was_argued_or_implied(tmp_path):
    write_sound_tree(tmp_path)
    write_decision(tmp_path, "dec-bare", rejected_alternatives=[{"option": "x", "reason": "y"}])
    assert messages(tmp_path) == ["rejected_alternatives.0.basis: missing field"]


def test_a_blank_verification_command_is_red(tmp_path):
    write_sound_tree(tmp_path)
    write_node(
        tmp_path,
        "uc-vague",
        "use-case",
        parent="fr-offline",
        verification=[{"command": "  "}],
    )
    assert messages(tmp_path) == ["verification.0.command: must not be blank"]


def test_an_id_that_is_not_lowercase_words_is_red(tmp_path):
    write_sound_tree(tmp_path)
    write_record(
        tmp_path,
        "uc-Shouty",
        node_frontmatter("uc-Shouty", "use-case", parent="fr-offline"),
        "body",
    )
    assert found(tmp_path) == [("uc-Shouty.md", "schema")]
    assert "lowercase words joined by hyphens" in messages(tmp_path)[0]


def test_a_state_outside_the_vocabulary_is_red(tmp_path):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "uc-odd", "use-case", parent="fr-offline", state="done")
    assert found(tmp_path) == [("uc-odd.md", "schema")]
    assert messages(tmp_path)[0].startswith("state: Input should be")


def test_a_multiline_title_is_red(tmp_path):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "uc-long", "use-case", parent="fr-offline", title="one\ntwo")
    assert found(tmp_path) == [("uc-long.md", "schema")]
    assert messages(tmp_path) == ["title: must be one line"]


# --------------------------------------------------------------------------------------------
# Identity
# --------------------------------------------------------------------------------------------


def test_two_files_claiming_one_id_are_both_reported(tmp_path):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "uc-edit", "use-case", parent="fr-offline", subdirectory="copy")
    assert sorted(found(tmp_path)) == [("uc-edit.md", "duplicate-id")] * 2
    assert all("also claimed by" in message for message in messages(tmp_path))


def test_an_id_that_is_not_the_filename_is_red(tmp_path):
    write_sound_tree(tmp_path)
    write_record(
        tmp_path,
        "uc-renamed",
        node_frontmatter("uc-original", "use-case", parent="fr-offline"),
        "b",
    )
    assert found(tmp_path) == [("uc-renamed.md", "id-filename-mismatch")]


def test_an_id_prefix_that_disagrees_with_the_type_is_red(tmp_path):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "fr-really-a-use-case", "use-case", parent="fr-offline")
    assert found(tmp_path) == [("fr-really-a-use-case.md", "id-prefix-mismatch")]


def test_a_decision_id_needs_the_decision_prefix(tmp_path):
    write_sound_tree(tmp_path)
    write_decision(tmp_path, "local-first-too")
    assert found(tmp_path) == [("local-first-too.md", "id-prefix-mismatch")]


# --------------------------------------------------------------------------------------------
# The tree edges
# --------------------------------------------------------------------------------------------


def test_a_use_case_without_a_parent_is_red(tmp_path):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "uc-loose", "use-case")
    assert found(tmp_path) == [("uc-loose.md", "parent-missing")]


def test_a_goal_with_a_parent_is_red(tmp_path):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "goal-nested", "goal", parent="goal-notes")
    assert found(tmp_path) == [("goal-nested.md", "goal-has-parent")]


def test_a_parent_that_does_not_exist_is_red(tmp_path):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "uc-orphan", "use-case", parent="fr-gone")
    assert found(tmp_path) == [("uc-orphan.md", "dangling-parent")]
    assert "no such node" in messages(tmp_path)[0]


def test_a_parent_that_is_a_decision_is_dangling(tmp_path):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "uc-orphan", "use-case", parent="dec-local-first")
    assert found(tmp_path) == [("uc-orphan.md", "dangling-parent")]
    assert "it is a decision, not a node" in messages(tmp_path)[0]


def test_a_use_case_directly_under_a_goal_is_the_wrong_combination(tmp_path):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "uc-skip", "use-case", parent="goal-notes")
    assert found(tmp_path) == [("uc-skip.md", "parent-type-mismatch")]


def test_a_requirement_under_a_use_case_is_the_wrong_combination(tmp_path):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "fr-upside-down", "functional-requirement", parent="uc-edit")
    assert found(tmp_path) == [("fr-upside-down.md", "parent-type-mismatch")]


def test_a_parent_cycle_is_reported_on_every_member(tmp_path):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "fr-a", "functional-requirement", parent="fr-b")
    write_node(tmp_path, "fr-b", "functional-requirement", parent="fr-a")
    cycle = sorted(pair for pair in found(tmp_path) if pair[1] == "parent-cycle")
    assert cycle == [("fr-a.md", "parent-cycle"), ("fr-b.md", "parent-cycle")]


def test_a_node_that_is_its_own_parent_is_a_cycle(tmp_path):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "fr-self", "functional-requirement", parent="fr-self")
    assert ("fr-self.md", "parent-cycle") in found(tmp_path)


# --------------------------------------------------------------------------------------------
# What a work node must carry
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fields",
    [
        {"mechanism": "pending"},
        {"implementation": "somewhere"},
        {"foundation": True},
        {"state": "improvised"},
        {
            "spikes": [
                {"question": "q", "outcome": "feasible", "finding": "f", "date": "2026-10-04"}
            ]
        },
    ],
)
def test_a_goal_cannot_carry_work_fields(tmp_path, fields):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "goal-busy", "goal", **fields)
    assert found(tmp_path) == [("goal-busy.md", "goal-carries-work-fields")]


def test_a_goal_may_carry_a_verification_because_it_is_acceptance_and_not_work(tmp_path):
    write_sound_tree(tmp_path)
    write_node(
        tmp_path,
        "goal-notes",
        "goal",
        decisions=["dec-local-first"],
        verification=[
            {"command": "scripts/check_notes_journey.sh", "expects": "the whole journey works"}
        ],
    )
    assert found(tmp_path) == []


def test_a_goal_with_a_verification_and_a_work_field_is_red_for_the_work_field_only(tmp_path):
    write_sound_tree(tmp_path)
    write_node(
        tmp_path,
        "goal-busy",
        "goal",
        mechanism="pending",
        verification=[{"command": "true"}],
    )
    assert found(tmp_path) == [("goal-busy.md", "goal-carries-work-fields")]
    assert messages(tmp_path) == ["a goal carries mechanism"]


def test_a_work_node_without_a_mechanism_is_red(tmp_path):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "uc-undecided", "use-case", parent="fr-offline", mechanism=None)
    assert found(tmp_path) == [("uc-undecided.md", "missing-work-field")]
    assert "write `pending` to defer it" in messages(tmp_path)[0]


def test_a_hardened_node_needs_an_implementation_and_a_verification(tmp_path):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "uc-built", "use-case", parent="fr-offline", state="hardened")
    assert sorted(found(tmp_path)) == [
        ("uc-built.md", "hardened-needs-implementation"),
        ("uc-built.md", "hardened-needs-verification"),
    ]


def test_a_hardened_node_with_both_is_green(tmp_path):
    write_sound_tree(tmp_path)
    write_node(
        tmp_path,
        "uc-built",
        "use-case",
        parent="fr-offline",
        state="hardened",
        implementation="app/notes.py::edit_note",
        verification=[{"command": "pytest tests/test_notes.py -q"}],
    )
    assert found(tmp_path) == []


def test_a_foundation_node_cannot_be_improvised(tmp_path):
    write_sound_tree(tmp_path)
    write_node(
        tmp_path,
        "uc-persistence",
        "use-case",
        parent="fr-offline",
        foundation=True,
        state="improvised",
    )
    assert found(tmp_path) == [("uc-persistence.md", "foundation-improvised")]


def test_a_foundation_node_may_go_straight_from_pending_to_hardened(tmp_path):
    write_sound_tree(tmp_path)
    write_node(
        tmp_path,
        "uc-persistence",
        "use-case",
        parent="fr-offline",
        foundation=True,
        state="hardened",
        implementation="app/store.py",
        verification=[{"command": "true"}],
    )
    assert found(tmp_path) == []


def test_improvised_and_pending_nodes_may_have_no_verification(tmp_path):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "uc-live", "use-case", parent="fr-offline", state="improvised")
    write_node(tmp_path, "uc-later", "use-case", parent="fr-offline")
    assert found(tmp_path) == []


# --------------------------------------------------------------------------------------------
# Decisions and the pointers to them
# --------------------------------------------------------------------------------------------


def test_a_pointer_to_a_decision_that_does_not_exist_is_red(tmp_path):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "uc-bound", "use-case", parent="fr-offline", decisions=["dec-ghost"])
    assert found(tmp_path) == [("uc-bound.md", "dangling-decision")]


def test_a_pointer_to_a_node_is_dangling_as_a_decision(tmp_path):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "uc-bound", "use-case", parent="fr-offline", decisions=["fr-offline"])
    assert found(tmp_path) == [("uc-bound.md", "dangling-decision")]
    assert "not a decision" in messages(tmp_path)[0]


def test_a_node_pointing_at_a_superseded_decision_is_told_the_live_successor(tmp_path):
    write_sound_tree(tmp_path)
    write_decision(tmp_path, "dec-old", state="superseded", superseded_by="dec-middle")
    write_decision(tmp_path, "dec-middle", state="superseded", superseded_by="dec-new")
    write_decision(tmp_path, "dec-new")
    write_node(tmp_path, "uc-bound", "use-case", parent="fr-offline", decisions=["dec-old"])
    assert found(tmp_path) == [("uc-bound.md", "superseded-decision-in-use")]
    assert "point at 'dec-new' instead" in messages(tmp_path)[0]


def test_a_node_pointing_at_an_under_review_decision_is_green(tmp_path):
    write_sound_tree(tmp_path)
    write_decision(tmp_path, "dec-challenged", state="under-review")
    write_node(tmp_path, "uc-bound", "use-case", parent="fr-offline", decisions=["dec-challenged"])
    assert found(tmp_path) == []


def test_a_superseded_decision_must_name_its_successor(tmp_path):
    write_sound_tree(tmp_path)
    write_decision(tmp_path, "dec-old", state="superseded")
    assert found(tmp_path) == [("dec-old.md", "superseded-without-successor")]


@pytest.mark.parametrize("state", ["in-force", "under-review"])
def test_a_decision_that_is_not_superseded_has_no_successor(tmp_path, state):
    write_sound_tree(tmp_path)
    write_decision(tmp_path, "dec-live", state=state, superseded_by="dec-local-first")
    assert found(tmp_path) == [("dec-live.md", "successor-without-supersession")]


def test_a_successor_that_does_not_exist_is_red(tmp_path):
    write_sound_tree(tmp_path)
    write_decision(tmp_path, "dec-old", state="superseded", superseded_by="dec-ghost")
    assert found(tmp_path) == [("dec-old.md", "dangling-successor")]


def test_a_successor_that_is_a_node_is_dangling_as_a_decision(tmp_path):
    write_sound_tree(tmp_path)
    write_decision(tmp_path, "dec-old", state="superseded", superseded_by="goal-notes")
    assert found(tmp_path) == [("dec-old.md", "dangling-successor")]


def test_a_chain_of_supersessions_ending_in_a_live_decision_is_green(tmp_path):
    write_sound_tree(tmp_path)
    write_decision(tmp_path, "dec-old", state="superseded", superseded_by="dec-middle")
    write_decision(tmp_path, "dec-middle", state="superseded", superseded_by="dec-local-first")
    assert found(tmp_path) == []


def test_supersession_that_loops_is_reported_on_every_member(tmp_path):
    write_sound_tree(tmp_path)
    write_decision(tmp_path, "dec-a", state="superseded", superseded_by="dec-b")
    write_decision(tmp_path, "dec-b", state="superseded", superseded_by="dec-a")
    assert sorted(found(tmp_path)) == [
        ("dec-a.md", "successor-cycle"),
        ("dec-b.md", "successor-cycle"),
    ]


def test_a_decision_superseded_by_itself_is_a_cycle(tmp_path):
    write_sound_tree(tmp_path)
    write_decision(tmp_path, "dec-self", state="superseded", superseded_by="dec-self")
    assert found(tmp_path) == [("dec-self.md", "successor-cycle")]


def test_friction_naming_a_node_that_does_not_exist_is_red(tmp_path):
    write_sound_tree(tmp_path)
    write_decision(
        tmp_path,
        "dec-hurting",
        friction=[{"date": "2026-10-05", "summary": "it hurt", "node": "uc-ghost"}],
    )
    assert found(tmp_path) == [("dec-hurting.md", "dangling-friction-node")]


def test_friction_naming_a_real_node_or_none_is_green(tmp_path):
    write_sound_tree(tmp_path)
    write_decision(
        tmp_path,
        "dec-hurting",
        friction=[
            {"date": "2026-10-05", "summary": "it hurt", "node": "uc-edit", "evidence": "PR 12"},
            {"date": "2026-10-06", "summary": "it hurt again"},
        ],
    )
    assert found(tmp_path) == []


# --------------------------------------------------------------------------------------------
# One fault is one report
# --------------------------------------------------------------------------------------------


def test_a_reference_to_a_file_that_failed_to_load_is_not_also_dangling(tmp_path):
    # The target is there and has its own defect; reporting the pointer to it too would say the
    # same fault twice.
    write_sound_tree(tmp_path)
    write_node(tmp_path, "fr-broken", "functional-requirement", parent="goal-notes", sources=None)
    write_node(tmp_path, "uc-child", "use-case", parent="fr-broken")
    assert found(tmp_path) == [("fr-broken.md", "schema")]


def test_defects_come_out_in_a_stable_order(tmp_path):
    write_sound_tree(tmp_path)
    (tmp_path / "zz.txt").write_text("x")
    (tmp_path / "aa.txt").write_text("x")
    write_node(tmp_path, "uc-loose", "use-case")
    assert [name for name, _ in found(tmp_path)] == ["aa.txt", "uc-loose.md", "zz.txt"]
