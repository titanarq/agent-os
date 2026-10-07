"""The v2 host's dispatch rules over issue rows: address, dependencies first, no shared code."""

from __future__ import annotations

import pytest
from compile_support import CONFIG, body, ticket_row

from agent_os.product.dispatch.markers import (
    parse_dependency_markers,
    parse_node_marker,
    parse_touched_paths,
)
from agent_os.product.dispatch.rules import (
    is_v2_host,
    rows_the_tree_rules_allow,
    tree_dispatch_refusals,
)
from agent_os.product.dispatch.touched_code import overlapping_paths, paths_named_in


def test_the_markers_round_trip_and_an_absent_one_reads_as_empty():
    text = body("uc-sync", depends_on=["uc-a", "uc-b"], touches=["app/sync.py", "docs/x.md"])
    assert parse_node_marker(text) == "uc-sync"
    assert parse_dependency_markers(text) == ("uc-a", "uc-b")
    assert parse_touched_paths(text) == ("app/sync.py", "docs/x.md")
    plain = body("uc-sync")
    assert parse_dependency_markers(plain) == () and parse_touched_paths(plain) == ()


def test_a_host_is_v2_only_when_it_says_so():
    assert not is_v2_host(CONFIG)
    CONFIG.tree.dispatch_by_node = True
    try:
        assert is_v2_host(CONFIG)
    finally:
        CONFIG.tree.dispatch_by_node = False


def test_a_ticket_with_no_address_is_refused():
    (reason,) = tree_dispatch_refusals(ticket_row(5, "a body with no marker"), [])
    assert "no node address" in reason


def test_a_ticket_with_a_clear_road_is_allowed():
    row = ticket_row(5, body("uc-sync", depends_on=["uc-a"], touches=["app/sync.py"]))
    assert tree_dispatch_refusals(row, [row]) == []


def test_a_ticket_waits_for_the_open_ticket_of_a_node_it_depends_on():
    first = ticket_row(4, body("uc-a"))
    second = ticket_row(5, body("uc-sync", depends_on=["uc-a"]))
    (reason,) = tree_dispatch_refusals(second, [first, second])
    assert "`uc-a`" in reason and "#4" in reason
    assert tree_dispatch_refusals(second, [second]) == []


@pytest.mark.parametrize(
    ("running_paths", "overlaps"),
    [
        (["app/sync.py"], True),
        (["app"], True),
        (["app/sync.py/"], True),
        (["app/sync.pyc"], False),
        (["docs/other.md"], False),
        ([], False),
    ],
)
def test_two_tickets_never_run_on_code_that_overlaps(running_paths, overlaps):
    candidate = ticket_row(5, body("uc-sync", touches=["app/sync.py"]))
    running = ticket_row(4, body("uc-a", touches=running_paths))
    reasons = tree_dispatch_refusals(candidate, [candidate, running], [running])
    assert bool(reasons) is overlaps
    if overlaps:
        assert "#4" in reasons[0]


def test_a_ticket_that_names_no_code_collides_with_nothing():
    candidate = ticket_row(5, body("uc-sync"))
    running = ticket_row(4, body("uc-a", touches=["app/sync.py"]))
    assert tree_dispatch_refusals(candidate, [candidate, running], [running]) == []


def test_the_scan_filter_is_the_identity_outside_a_v2_host():
    rows = [ticket_row(1, "no marker")]
    assert rows_the_tree_rules_allow(rows, rows, CONFIG) == rows


def test_the_scan_filter_drops_unaddressed_and_blocked_tickets_in_a_v2_host():
    config = CONFIG.model_copy(deep=True)
    config.tree.dispatch_by_node = True
    free = ticket_row(1, body("uc-a"))
    blocked = ticket_row(2, body("uc-b", depends_on=["uc-a"]))
    unaddressed = ticket_row(3, "no marker")
    allowed = rows_the_tree_rules_allow([free, blocked, unaddressed], [free, blocked], config)
    assert allowed == [free]


def test_paths_are_read_out_of_prose_and_overlap_is_by_directory():
    text = '`agent_os/quality/` (the CI ratchet), prompts/validator.md ("x"), e.g. #114 v1.2'
    assert paths_named_in(text) == ("agent_os/quality", "prompts/validator.md")
    assert overlapping_paths(["agent_os/quality"], ["agent_os/quality/cli.py"]) == [
        "agent_os/quality"
    ]
    assert overlapping_paths(["agent_os/qual"], ["agent_os/quality"]) == []
