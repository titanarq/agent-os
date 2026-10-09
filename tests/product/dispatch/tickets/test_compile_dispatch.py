"""What `compile` writes into a ticket for dispatch: its address, dependencies and touched code."""

from __future__ import annotations

import pytest
from compile_support import body, compiled, one_ticket, ticket_row
from tree_helpers import experiment_entry, write_node, write_sound_tree

from agent_os.product.dispatch.markers import (
    parse_dependency_markers,
    parse_node_marker,
    parse_touched_paths,
)
from agent_os.product.dispatch.rules import tree_dispatch_refusals
from agent_os.product.tree.checks import check_tree
from agent_os.product.tree.compile import CompileError
from agent_os.product.tree.loader import load_tree


def two_use_cases(root, **second_fields):
    write_sound_tree(root)
    write_node(
        root,
        "uc-sync",
        "use-case",
        parent="fr-offline",
        verification=[{"command": "true"}],
        **second_fields,
    )


def test_a_ticket_carries_the_node_it_depends_on_in_a_marker_and_in_the_section(tmp_path):
    two_use_cases(tmp_path, depends_on=["uc-edit"])
    ticket = one_ticket(tmp_path, "uc-sync")
    assert ticket.depends_on == ("uc-edit",)
    assert parse_dependency_markers(ticket.body) == ("uc-edit",)
    dependencies = ticket.body.split("## Dependencies\n")[1].split("\n\n## ")[0]
    assert "`uc-edit`" in dependencies
    assert parse_dependency_markers(one_ticket(tmp_path, "uc-edit").body) == ()
    assert one_ticket(tmp_path, "uc-edit").body.split("## Dependencies\n")[1].startswith("none")


def test_a_dependency_is_ordered_before_what_depends_on_it(tmp_path):
    # `uc-edit` sorts before `uc-sync` anyway, so the dependency points the other way.
    two_use_cases(tmp_path)
    write_node(
        tmp_path,
        "uc-edit",
        "use-case",
        parent="fr-offline",
        verification=[{"command": "true"}],
        depends_on=["uc-sync"],
    )
    assert [t.node_id for t in compiled(tmp_path).tickets] == ["uc-sync", "uc-edit"]


def test_a_transitive_dependency_orders_through_a_node_that_is_not_a_ticket(tmp_path):
    two_use_cases(tmp_path)
    write_node(tmp_path, "uc-aaa", "use-case", parent="fr-offline", depends_on=["uc-zzz"])
    write_node(
        tmp_path, "uc-zzz", "use-case", parent="fr-offline", state="improvised", depends_on=[]
    )
    order = [t.node_id for t in compiled(tmp_path).tickets]
    assert order.index("uc-edit") < order.index("uc-sync")


def test_the_touched_paths_are_the_ones_the_node_names(tmp_path):
    two_use_cases(
        tmp_path,
        implementation="app/sync.py (`push`), docs/sync.md and pull request #12",
        mechanism="A queue in app/queue/ drained by app/sync.py.",
    )
    ticket = one_ticket(tmp_path, "uc-sync")
    assert set(ticket.touched_paths) == {"app/sync.py", "docs/sync.md", "app/queue"}
    assert set(parse_touched_paths(ticket.body)) == set(ticket.touched_paths)
    assert parse_node_marker(ticket.body) == "uc-sync"


# What the prose of `implementation` and `mechanism` names is read as paths: any word with a slash or
# a file extension. That is wrong for `http.client`, `p.ej` or a document mentioned in passing.
PROSE_THAT_MISFIRES = (
    "Built on http.client, as p.ej in docs/VECTOR.md, but only app/sync.py changes."
)


def test_without_a_touches_field_the_prose_is_still_read_for_paths(tmp_path):
    two_use_cases(tmp_path, implementation=PROSE_THAT_MISFIRES)
    assert set(one_ticket(tmp_path, "uc-sync").touched_paths) == {
        "http.client",
        "p.ej",
        "docs/VECTOR.md",
        "app/sync.py",
    }


def test_a_touches_field_decides_the_touched_paths_and_the_prose_is_not_read(tmp_path):
    two_use_cases(
        tmp_path,
        implementation=PROSE_THAT_MISFIRES,
        mechanism="A queue in app/queue/ drained by app/sync.py.",
        touches=["app/sync.py", "app/queue"],
    )
    ticket = one_ticket(tmp_path, "uc-sync")
    assert ticket.touched_paths == ("app/sync.py", "app/queue")
    assert parse_touched_paths(ticket.body) == ticket.touched_paths


def test_an_empty_touches_field_says_the_node_touches_no_known_code(tmp_path):
    two_use_cases(tmp_path, implementation=PROSE_THAT_MISFIRES, touches=[])
    ticket = one_ticket(tmp_path, "uc-sync")
    assert ticket.touched_paths == ()
    assert "<!-- touches:" not in ticket.body


def test_declared_paths_are_written_the_way_derived_ones_are(tmp_path):
    two_use_cases(tmp_path, touches=["./app/queue/", "app/sync.py", "app/sync.py"])
    assert one_ticket(tmp_path, "uc-sync").touched_paths == ("app/queue", "app/sync.py")


@pytest.mark.parametrize(
    ("path", "reason"),
    [
        ("app sync.py", "single word"),
        ("app/a,app/b", "single word"),
        ("app/a-->b", "single word"),
        ("  ", "single word"),
        (".", "under the host's root"),
        ("./", "under the host's root"),
        ("/", "under the host's root"),
    ],
)
def test_a_touched_path_the_ticket_marker_cannot_carry_is_a_schema_defect(tmp_path, path, reason):
    two_use_cases(tmp_path, touches=[path])
    (defect,) = check_tree(load_tree(tmp_path))
    assert (defect.path.name, defect.code) == ("uc-sync.md", "schema")
    assert reason in defect.message


def test_dispatch_compares_the_declared_paths_and_not_the_words_of_the_prose(tmp_path):
    two_use_cases(
        tmp_path,
        implementation=PROSE_THAT_MISFIRES,
        touches=["app/sync.py"],
    )
    write_node(
        tmp_path,
        "uc-docs",
        "use-case",
        parent="fr-offline",
        implementation=PROSE_THAT_MISFIRES,
        touches=["docs/sync.md"],
    )
    sync = ticket_row(1, one_ticket(tmp_path, "uc-sync").body)
    docs = ticket_row(2, one_ticket(tmp_path, "uc-docs").body)
    assert tree_dispatch_refusals(docs, [sync, docs], [sync]) == []
    same_code = ticket_row(3, body("uc-other", touches=["app/sync.py"]))
    assert tree_dispatch_refusals(same_code, [sync, same_code], [sync]) == [
        "it touches app/sync.py, which running ticket #1 touches too"
    ]


def test_a_node_that_names_no_path_has_no_touches_marker(tmp_path):
    write_sound_tree(tmp_path)
    ticket = one_ticket(tmp_path, "uc-edit")
    assert ticket.touched_paths == ()
    assert "<!-- touches:" not in ticket.body


def test_a_ticket_builds_and_leaves_the_node_implemented_never_hardened(tmp_path):
    write_sound_tree(tmp_path)
    done = one_ticket(tmp_path, "uc-edit").body.split("## Definition of done\n")[1]
    assert "`state: implemented`" in done
    assert "state: hardened" not in done
    assert "cannot be hardened yet" not in done


def test_a_ticket_says_why_its_node_cannot_be_hardened_yet(tmp_path):
    write_sound_tree(tmp_path)
    write_node(
        tmp_path,
        "uc-edit",
        "use-case",
        parent="fr-offline",
        verification=[{"command": "true"}],
        experiments=[
            experiment_entry(
                "open", kind="question", scope="what", default_answer="yes", question="Which?"
            )
        ],
    )
    done = one_ticket(tmp_path, "uc-edit").body.split("## Definition of done\n")[1]
    assert "cannot be hardened yet" in done and "open-what-question" in done
    assert "state: hardened" not in done


def test_a_node_whose_dependency_is_challenged_cannot_be_hardened_either(tmp_path):
    two_use_cases(tmp_path, depends_on=["uc-edit"])
    write_node(
        tmp_path,
        "uc-edit",
        "use-case",
        parent="fr-offline",
        verification=[{"command": "true"}],
        challenge={"reason": "over-cost"},
    )
    done = one_ticket(tmp_path, "uc-sync").body.split("## Definition of done\n")[1]
    assert "`uc-edit`: challenge:over-cost" in done


def write_requirement_with_use_case(root, requirement_id, use_case_id, **requirement_fields):
    write_node(
        root,
        requirement_id,
        "functional-requirement",
        parent="goal-notes",
        **requirement_fields,
    )
    write_node(
        root,
        use_case_id,
        "use-case",
        parent=requirement_id,
        verification=[{"command": "true"}],
    )


def test_a_use_case_inherits_the_dependencies_of_its_requirement(tmp_path):
    write_sound_tree(tmp_path)
    # `fr-aaa-ui` sorts before `fr-zzz-base`, so only the inherited edge can put its use case last.
    write_node(tmp_path, "fr-zzz-base", "functional-requirement", parent="goal-notes")
    write_node(
        tmp_path,
        "uc-base-skeleton",
        "use-case",
        parent="fr-zzz-base",
        verification=[{"command": "true"}],
    )
    write_requirement_with_use_case(
        tmp_path, "fr-aaa-ui", "uc-aaa-screen", depends_on=["uc-base-skeleton"]
    )
    order = [t.node_id for t in compiled(tmp_path).tickets]
    assert order.index("uc-base-skeleton") < order.index("uc-aaa-screen")
    ticket = one_ticket(tmp_path, "uc-aaa-screen")
    assert ticket.depends_on == ("uc-base-skeleton",)
    assert parse_dependency_markers(ticket.body) == ("uc-base-skeleton",)


def test_a_dependency_on_a_requirement_waits_for_the_use_cases_under_it(tmp_path):
    write_sound_tree(tmp_path)
    write_requirement_with_use_case(tmp_path, "fr-zzz-base", "uc-zzz-boot")
    write_requirement_with_use_case(
        tmp_path, "fr-aaa-ui", "uc-aaa-screen", depends_on=["fr-zzz-base"]
    )
    order = [t.node_id for t in compiled(tmp_path).tickets]
    assert order.index("uc-zzz-boot") < order.index("uc-aaa-screen")
    assert "uc-zzz-boot" in one_ticket(tmp_path, "uc-aaa-screen").depends_on


def test_a_use_case_under_a_foundation_requirement_is_not_a_foundation_by_inheritance(tmp_path):
    # The owner, 2026-10-09: "not every use case under a foundation is indispensable". `uc-zzz-boot`
    # sorts after `uc-edit`, so being ordered ahead of it would take a flag it does not carry.
    write_sound_tree(tmp_path)
    write_requirement_with_use_case(tmp_path, "fr-zzz-base", "uc-zzz-boot", foundation=True)
    order = [t.node_id for t in compiled(tmp_path).tickets]
    assert order.index("uc-edit") < order.index("uc-zzz-boot")


def test_a_use_case_the_expert_flags_under_a_foundation_requirement_is_ordered_as_a_foundation(
    tmp_path,
):
    write_sound_tree(tmp_path)
    write_requirement_with_use_case(tmp_path, "fr-zzz-base", "uc-zzz-boot", foundation=True)
    write_node(
        tmp_path,
        "uc-zzz-persistence",
        "use-case",
        parent="fr-zzz-base",
        foundation=True,
        verification=[{"command": "true"}],
    )
    order = [t.node_id for t in compiled(tmp_path).tickets]
    assert order.index("uc-zzz-persistence") < order.index("uc-edit") < order.index("uc-zzz-boot")


def test_inherited_dependencies_that_loop_are_refused_instead_of_hanging(tmp_path):
    write_sound_tree(tmp_path)
    write_requirement_with_use_case(tmp_path, "fr-aaa", "uc-aaa", depends_on=["uc-zzz"])
    write_requirement_with_use_case(tmp_path, "fr-zzz", "uc-zzz", depends_on=["uc-aaa"])
    with pytest.raises(CompileError, match="uc-aaa"):
        compiled(tmp_path)
