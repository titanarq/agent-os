"""A ticket waits for tickets: a dependency that never gets one is replaced by what it waits for.

Dispatch starts a ticket only once no open ticket belongs to a node it depends on
(`agent_os.product.dispatch.rules`), so a dependency on a node that has no ticket -- one already
`improvised` or `implemented`, which a puntal or deployed code serves -- waits for nothing. Left in
the `depends-on` marker it also hides the nodes that node itself waits for, and the ticket could be
dispatched before the foundations under it. `docs/tree/dec-dispatch-never-runs-two-tickets-on-the-same-code.md`:
dependent tickets are ordered, never run together.
"""

from __future__ import annotations

from compile_support import body, compiled, one_ticket, ticket_row
from tree_helpers import write_node, write_sound_tree

from agent_os.product.dispatch.markers import parse_dependency_markers
from agent_os.product.dispatch.rules import tree_dispatch_refusals


def write_use_case(root, node_id, **fields):
    write_node(root, node_id, "use-case", parent="fr-offline", **fields)


def test_a_dependency_without_a_ticket_is_replaced_by_the_dependencies_it_has(tmp_path):
    write_sound_tree(tmp_path)
    write_use_case(tmp_path, "uc-base")
    write_use_case(tmp_path, "uc-served", state="improvised", depends_on=["uc-base"])
    write_use_case(tmp_path, "uc-top", depends_on=["uc-served"])
    ticket = one_ticket(tmp_path, "uc-top")
    assert ticket.depends_on == ("uc-base",)
    assert parse_dependency_markers(ticket.body) == ("uc-base",)
    assert "`uc-served`" not in ticket.body.split("## Dependencies\n")[1].split("\n\n## ")[0]


def test_the_replacement_goes_down_as_many_levels_as_there_are_nodes_without_a_ticket(tmp_path):
    write_sound_tree(tmp_path)
    write_use_case(tmp_path, "uc-base")
    write_use_case(tmp_path, "uc-implemented", state="implemented", depends_on=["uc-base"])
    write_use_case(tmp_path, "uc-improvised", state="improvised", depends_on=["uc-implemented"])
    write_use_case(tmp_path, "uc-top", depends_on=["uc-improvised"])
    assert one_ticket(tmp_path, "uc-top").depends_on == ("uc-base",)


def test_a_dependency_that_has_a_ticket_is_kept_and_its_own_dependencies_are_not_copied(tmp_path):
    write_sound_tree(tmp_path)
    write_use_case(tmp_path, "uc-base")
    write_use_case(tmp_path, "uc-middle", depends_on=["uc-base"])
    write_use_case(tmp_path, "uc-top", depends_on=["uc-middle"])
    assert one_ticket(tmp_path, "uc-top").depends_on == ("uc-middle",)


def test_a_dependency_without_a_ticket_and_without_dependencies_leaves_nothing_to_wait_for(
    tmp_path,
):
    write_sound_tree(tmp_path)
    write_use_case(tmp_path, "uc-served", state="improvised")
    write_use_case(tmp_path, "uc-top", depends_on=["uc-served"])
    ticket = one_ticket(tmp_path, "uc-top")
    assert ticket.depends_on == ()
    assert "<!-- depends-on:" not in ticket.body
    assert ticket.body.split("## Dependencies\n")[1].startswith("none")


def test_several_routes_to_the_same_ticket_name_it_once_in_the_order_they_are_met(tmp_path):
    write_sound_tree(tmp_path)
    write_use_case(tmp_path, "uc-base")
    write_use_case(tmp_path, "uc-other")
    write_use_case(tmp_path, "uc-left", state="improvised", depends_on=["uc-base", "uc-other"])
    write_use_case(tmp_path, "uc-right", state="improvised", depends_on=["uc-base"])
    write_use_case(tmp_path, "uc-top", depends_on=["uc-left", "uc-right"])
    assert one_ticket(tmp_path, "uc-top").depends_on == ("uc-base", "uc-other")


def test_what_a_requirement_above_a_node_without_a_ticket_waits_for_is_inherited_too(tmp_path):
    write_sound_tree(tmp_path)
    write_use_case(tmp_path, "uc-base")
    write_node(
        tmp_path,
        "fr-served",
        "functional-requirement",
        parent="goal-notes",
        depends_on=["uc-base"],
    )
    write_node(tmp_path, "uc-served", "use-case", parent="fr-served", state="improvised")
    write_use_case(tmp_path, "uc-top", depends_on=["uc-served"])
    assert one_ticket(tmp_path, "uc-top").depends_on == ("uc-base",)


def test_dispatch_holds_the_ticket_while_the_ticket_under_a_node_without_one_is_open(tmp_path):
    write_sound_tree(tmp_path)
    write_use_case(tmp_path, "uc-base")
    write_use_case(tmp_path, "uc-served", state="improvised", depends_on=["uc-base"])
    write_use_case(tmp_path, "uc-top", depends_on=["uc-served"])
    top = ticket_row(2, one_ticket(tmp_path, "uc-top").body)
    base = ticket_row(1, body("uc-base"))
    refusals = tree_dispatch_refusals(top, [base, top])
    assert refusals == ["it depends on node `uc-base`, whose ticket #1 is still open"]
    assert tree_dispatch_refusals(top, [top]) == []


def test_every_ticket_of_a_compile_depends_only_on_nodes_that_have_one(tmp_path):
    write_sound_tree(tmp_path)
    write_use_case(tmp_path, "uc-base")
    write_use_case(tmp_path, "uc-served", state="improvised", depends_on=["uc-base"])
    write_use_case(tmp_path, "uc-top", depends_on=["uc-served", "uc-edit"])
    tickets = compiled(tmp_path).tickets
    with_a_ticket = {ticket.node_id for ticket in tickets}
    assert all(set(ticket.depends_on) <= with_a_ticket for ticket in tickets)
