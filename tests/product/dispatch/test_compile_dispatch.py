"""What `compile` writes into a ticket for dispatch: its address, dependencies and touched code."""

from __future__ import annotations

from compile_support import compiled, one_ticket
from tree_helpers import experiment_entry, write_node, write_sound_tree

from agent_os.product.dispatch.markers import (
    parse_dependency_markers,
    parse_node_marker,
    parse_touched_paths,
)


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
