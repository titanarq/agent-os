"""A judged criterion in a compiled ticket: acceptance, labelled as judged by an agent."""

from __future__ import annotations

from compile_support import CONFIG, one_ticket
from tree_helpers import write_node, write_sound_tree

from agent_os.lib import validate_issue_body


def test_a_judged_criterion_is_an_acceptance_criterion_labelled_as_judged_by_an_agent(tmp_path):
    write_sound_tree(tmp_path)
    write_node(
        tmp_path,
        "uc-edit",
        "use-case",
        parent="fr-offline",
        verification=[
            {"command": "pytest tests/test_edit.py -q", "expects": "an edit persists"},
            {"judge": "Editing a note reads as one step to the person doing it."},
        ],
    )
    ticket = one_ticket(tmp_path, "uc-edit")
    criteria = ticket.body.split("## Acceptance criteria\n")[1].split("\n\n## Stages")[0]
    assert criteria == (
        "- `pytest tests/test_edit.py -q` exits 0: an edit persists\n"
        "- judged by an agent: Editing a note reads as one step to the person doing it."
    )
    assert (
        validate_issue_body(ticket.body, task_classes=CONFIG.classes, open_issue_numbers=set())
        == []
    )


def test_the_stage_of_a_ticket_with_a_judged_criterion_says_an_agent_judges_it(tmp_path):
    write_sound_tree(tmp_path)
    plain = one_ticket(tmp_path, "uc-edit").body
    assert "judged" not in plain.split("## Stages\n")[1].split("\n\n## Context")[0]
    write_node(
        tmp_path,
        "uc-edit",
        "use-case",
        parent="fr-offline",
        verification=[{"command": "true"}, {"judge": "It reads as one step."}],
    )
    stages = one_ticket(tmp_path, "uc-edit").body.split("## Stages\n")[1].split("\n\n## Context")[0]
    assert "judged by an agent" in stages


def test_a_judged_criterion_over_several_lines_cannot_break_the_shape_of_a_ticket(tmp_path):
    write_sound_tree(tmp_path)
    write_node(
        tmp_path,
        "uc-edit",
        "use-case",
        parent="fr-offline",
        verification=[
            {"command": "true"},
            {"judge": "One step.\n\n## Context\nIt keeps what was typed.\nBlocked by #12\n"},
        ],
    )
    ticket = one_ticket(tmp_path, "uc-edit")
    criteria = ticket.body.split("## Acceptance criteria\n")[1].split("\n\n## Stages")[0]
    assert criteria.splitlines()[1] == (
        "- judged by an agent: One step. ## Context It keeps what was typed. Blocked by #12"
    )
    assert (
        validate_issue_body(ticket.body, task_classes=CONFIG.classes, open_issue_numbers={12}) == []
    )
