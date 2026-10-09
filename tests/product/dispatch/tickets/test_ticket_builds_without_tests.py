"""A ticket builds: it asks for no test of the node, and a node with no verification of its own is
accepted by criteria derived from its description and from the acceptance of its ancestors.

`docs/tree/dec-tests-harden-they-do-not-build.md` (an implemented node passes the essential top-down
acceptance and then the owner's use; tests come when it hardens, "foundations follow the same rule")
and `docs/tree/dec-top-down-acceptance-is-essential-even-when-judged.md` (the acceptance holds from
the first build, even when an agent judges it).
"""

from __future__ import annotations

import pytest
from compile_support import CONFIG, one_ticket
from tree_helpers import experiment_entry, write_node, write_sound_tree

from agent_os.lib import validate_issue_body


def section(body: str, heading: str) -> str:
    return body.split(f"## {heading}\n")[1].split("\n\n## ")[0]


def write_use_case(root, **fields):
    write_node(root, "uc-built", "use-case", parent="fr-offline", **fields)


VERIFICATIONS = {
    "a command": [{"command": "scripts/check_built.sh"}],
    "a judged criterion": [{"judge": "Editing a note reads as one step."}],
    "a command and a judged criterion": [
        {"command": "scripts/check_built.sh"},
        {"judge": "Editing a note reads as one step."},
    ],
    "nothing": [],
}


@pytest.mark.parametrize("verification", VERIFICATIONS.values(), ids=VERIFICATIONS)
def test_a_ticket_asks_for_no_test_of_the_node_it_builds(tmp_path, verification):
    write_sound_tree(tmp_path)
    write_use_case(tmp_path, verification=verification)
    body = one_ticket(tmp_path, "uc-built").body
    assert "project's tests" not in body
    assert "Tests and documentation" not in body
    done = section(body, "Definition of done")
    assert "No test is written for this node" in done
    assert "docs/tree/dec-tests-harden-they-do-not-build.md" in done
    assert "the tests the project already has must keep passing" in done
    assert "state: hardened" not in done


@pytest.mark.parametrize("verification", VERIFICATIONS.values(), ids=VERIFICATIONS)
def test_the_implementation_stage_is_verified_by_the_acceptance_and_then_by_use(
    tmp_path, verification
):
    write_sound_tree(tmp_path)
    write_use_case(tmp_path, verification=verification)
    stage = section(one_ticket(tmp_path, "uc-built").body, "Stages")
    assert "verified by" in stage and "tests" not in stage
    assert stage.rstrip().endswith("and then the owner's use")


def test_a_blocked_hardening_is_said_once_and_never_as_an_order_to_write_tests(tmp_path):
    write_sound_tree(tmp_path)
    write_use_case(
        tmp_path,
        verification=[{"command": "true"}],
        experiments=[
            experiment_entry(
                "open", kind="question", scope="what", default_answer="yes", question="Which?"
            )
        ],
    )
    done = section(one_ticket(tmp_path, "uc-built").body, "Definition of done")
    assert "open-what-question" in done
    mentions_of_tests = [line for line in done.splitlines() if "test" in line.lower()]
    assert len(mentions_of_tests) == 1 and "No test is written" in mentions_of_tests[0]
    assert "hardening tests" not in done


def test_the_documentation_the_project_asks_for_is_still_part_of_done(tmp_path):
    write_sound_tree(tmp_path)
    done = section(one_ticket(tmp_path, "uc-edit").body, "Definition of done")
    assert "Documentation as the project's AGENTS.md asks" in done


# --- a node with no verification of its own -----------------------------------------------------


def criteria_of(body: str) -> list[str]:
    return section(body, "Acceptance criteria").splitlines()


def still_holds(ancestor: str, what: str) -> str:
    return f"- judged by an agent: with `uc-built` built, `{ancestor}` still holds: {what}"


def test_a_node_without_verification_is_accepted_by_its_description_and_by_its_ancestors(tmp_path):
    write_sound_tree(tmp_path)
    write_node(
        tmp_path,
        "fr-offline",
        "functional-requirement",
        parent="goal-notes",
        verification=[
            {"command": "scripts/check_offline.sh", "expects": "every note opens offline"},
            {"judge": "Nothing\n\n## Context\nis lost when the connection drops."},
        ],
    )
    write_use_case(tmp_path)
    ticket = one_ticket(tmp_path, "uc-built")
    assert criteria_of(ticket.body) == [
        "- judged by an agent: `uc-built` does what its description says (the Objective above)",
        still_holds("fr-offline", "`scripts/check_offline.sh` exits 0: every note opens offline"),
        still_holds("fr-offline", "Nothing ## Context is lost when the connection drops."),
        still_holds("goal-notes", "An agent finds that goal-notes holds."),
    ]
    assert (
        validate_issue_body(ticket.body, task_classes=CONFIG.classes, open_issue_numbers=set())
        == []
    )


def test_a_node_without_verification_under_ancestors_without_any_keeps_the_goals_criterion(
    tmp_path,
):
    write_sound_tree(tmp_path)
    write_use_case(tmp_path)
    assert criteria_of(one_ticket(tmp_path, "uc-built").body)[1:] == [
        still_holds("goal-notes", "An agent finds that goal-notes holds.")
    ]


def test_a_node_with_a_verification_of_its_own_keeps_exactly_that_acceptance(tmp_path):
    write_sound_tree(tmp_path)
    write_use_case(tmp_path, verification=[{"command": "scripts/check_built.sh"}])
    assert criteria_of(one_ticket(tmp_path, "uc-built").body) == [
        "- `scripts/check_built.sh` exits 0"
    ]
