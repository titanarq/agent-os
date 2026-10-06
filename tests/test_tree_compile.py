"""`agent_os.tree.compile`: dispatch tickets from dispatchable nodes, escalations from the rest.

The shape of a ticket is judged by the repository's own `validate_issue_body` and `is_dispatchable`
-- the single implementation of "a brief an agent could start from" -- not by a copy of its rules
here. `compile` only renders: nothing in this file touches `gh`, a network or a backend.

Pure filesystem under `tmp_path`.
"""

from __future__ import annotations

import json
import pathlib
import subprocess

import pytest
from conftest import EXAMPLE_CONFIG
from tree_helpers import write_decision, write_node, write_sound_tree

from agent_os import issues
from agent_os.lib import is_dispatchable, load_agents_config, validate_issue_body
from agent_os.tree.compile import (
    CompileError,
    compile_as_data,
    compile_tree,
    parse_node_marker,
    render_compile_json,
    render_compile_text,
    write_compile_files,
)
from agent_os.tree.loader import load_tree

CONFIG = load_agents_config(EXAMPLE_CONFIG)
BUDGET_CLASS = "mechanical-qwen"


def compiled(root: pathlib.Path, **overrides):
    options = {"budget_class": BUDGET_CLASS, "tree_root": "product", **overrides}
    return compile_tree(load_tree(root), CONFIG, **options)


def one_ticket(root: pathlib.Path, node_id: str):
    (ticket,) = [t for t in compiled(root).tickets if t.node_id == node_id]
    return ticket


# --------------------------------------------------------------------------------------------
# The shape of a ticket
# --------------------------------------------------------------------------------------------


def test_a_ticket_is_a_body_the_dispatcher_accepts(tmp_path):
    write_sound_tree(tmp_path)
    ticket = one_ticket(tmp_path, "uc-edit")
    assert (
        validate_issue_body(ticket.body, task_classes=CONFIG.classes, open_issue_numbers=set())
        == []
    )
    issue = {
        "state": "OPEN",
        "labels": [{"name": "status:ready"}],
        "body": ticket.body,
    }
    assert is_dispatchable(issue, task_classes=CONFIG.classes, open_issue_numbers=set())


def test_a_ticket_names_its_node_in_a_machine_readable_marker(tmp_path):
    write_sound_tree(tmp_path)
    ticket = one_ticket(tmp_path, "uc-edit")
    assert ticket.body.rstrip().endswith("<!-- node: uc-edit -->")
    assert parse_node_marker(ticket.body) == "uc-edit"
    assert parse_node_marker("a body with no marker") is None
    assert parse_node_marker("") is None


def test_the_budget_line_is_the_class_the_ticket_was_compiled_with(tmp_path):
    write_sound_tree(tmp_path)
    ticket = one_ticket(tmp_path, "uc-edit")
    assert "<!-- budget: mechanical-qwen -->" in ticket.body
    assert ticket.budget_class == "mechanical-qwen"
    other = compiled(tmp_path, budget_class="complex-qwen").tickets[0]
    assert "<!-- budget: complex-qwen -->" in other.body


def test_the_verification_is_the_acceptance_criteria(tmp_path):
    write_sound_tree(tmp_path)
    write_node(
        tmp_path,
        "uc-edit",
        "use-case",
        parent="fr-offline",
        verification=[
            {"command": "pytest tests/test_edit.py -q", "expects": "an edit persists"},
            {"command": "scripts/check_sync.sh"},
        ],
    )
    criteria = one_ticket(tmp_path, "uc-edit").body.split("## Acceptance criteria\n")[1]
    criteria = criteria.split("\n\n## Stages")[0]
    assert criteria == (
        "- `pytest tests/test_edit.py -q` exits 0: an edit persists\n"
        "- `scripts/check_sync.sh` exits 0"
    )


def test_the_objective_is_the_node_and_its_description(tmp_path):
    write_sound_tree(tmp_path)
    objective = one_ticket(tmp_path, "uc-edit").body.split("## Objective\n")[1]
    objective = objective.split("\n\n## Acceptance criteria")[0]
    assert objective.startswith("Build the use-case `uc-edit`: Title of uc-edit")
    assert objective.endswith("Description of uc-edit.")


def test_the_context_is_the_slice_of_the_node_and_nothing_of_the_rest_of_the_tree(tmp_path):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "uc-sibling", "use-case", parent="fr-offline", body="SIBLING TEXT")
    write_decision(tmp_path, "dec-unrelated", body="UNRELATED TEXT")
    context = one_ticket(tmp_path, "uc-edit").body.split("## Context\n")[1]
    context = context.split("\n\n## Not included")[0]
    assert "Description of fr-offline." in context
    assert "Description of goal-notes." in context
    assert "`dec-local-first`" in context
    assert "SIBLING TEXT" not in context
    assert "UNRELATED TEXT" not in context


def test_a_pending_mechanism_adds_a_stage_that_writes_it_back(tmp_path):
    write_sound_tree(tmp_path)
    body = one_ticket(tmp_path, "uc-edit").body
    stages = body.split("## Stages\n")[1].split("\n\n## Context")[0].splitlines()
    assert len(stages) == 2
    assert stages[0].startswith("- [ ] Resolve the solution mechanism of `uc-edit`")
    assert "product/uc-edit.md" in stages[0]


def test_a_known_mechanism_is_one_stage_and_is_carried_in_the_context(tmp_path):
    write_sound_tree(tmp_path)
    write_node(
        tmp_path,
        "uc-edit",
        "use-case",
        parent="fr-offline",
        mechanism="Write through a local SQLite file",
        verification=[{"command": "true"}],
    )
    body = one_ticket(tmp_path, "uc-edit").body
    stages = body.split("## Stages\n")[1].split("\n\n## Context")[0].splitlines()
    assert len(stages) == 1
    assert "Write through a local SQLite file" in body


def test_the_title_takes_the_prefix_the_hosts_task_template_declares(tmp_path, monkeypatch):
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "task.md").write_text("---\nname: Task\ntitle: '[task] '\n---\nbody\n")
    monkeypatch.setattr(issues, "TEMPLATE_DIR", templates)
    tree = tmp_path / "tree"
    tree.mkdir()
    write_sound_tree(tree)
    assert one_ticket(tree, "uc-edit").title == "[task] Title of uc-edit"


def test_labels_are_the_type_label_the_configured_ones_and_the_requested_ones(tmp_path):
    write_sound_tree(tmp_path)
    config = load_agents_config(EXAMPLE_CONFIG)
    config.tree.ticket_labels = ["from-tree", "module:core"]
    result = compile_tree(
        load_tree(tmp_path),
        config,
        budget_class=BUDGET_CLASS,
        tree_root="product",
        extra_labels=["p2", "from-tree"],
    )
    assert result.tickets[0].labels == ("type:task", "from-tree", "module:core", "p2")


def test_a_description_that_would_break_the_issue_shape_is_refused_loudly(tmp_path):
    write_sound_tree(tmp_path)
    write_node(
        tmp_path,
        "uc-edit",
        "use-case",
        parent="fr-offline",
        body="First line.\n\n## Context\nA heading of the ticket, inside the description.",
        verification=[{"command": "true"}],
    )
    with pytest.raises(CompileError, match="not a dispatchable issue body"):
        compiled(tmp_path)


# --------------------------------------------------------------------------------------------
# What is a ticket and what escalates
# --------------------------------------------------------------------------------------------


def test_a_leaf_without_a_verification_escalates_and_is_never_a_ticket(tmp_path):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "uc-vague", "use-case", parent="fr-offline")
    result = compiled(tmp_path)
    assert [t.node_id for t in result.tickets] == ["uc-edit"]
    (escalation,) = result.escalations
    assert escalation.node_id == "uc-vague"
    assert escalation.code == "missing-verification"
    assert escalation.path == "product/uc-vague.md"
    assert "escalates instead of dispatching" in escalation.message


def test_a_requirement_with_use_cases_and_no_verification_is_a_container_and_skipped(tmp_path):
    write_sound_tree(tmp_path)
    result = compiled(tmp_path)
    assert result.escalations == ()
    assert result.containers == 1  # fr-offline: its use case is the work
    assert [t.node_id for t in result.tickets] == ["uc-edit"]


def test_a_requirement_with_use_cases_and_a_verification_of_its_own_is_still_a_container(tmp_path):
    write_sound_tree(tmp_path)
    write_node(
        tmp_path,
        "fr-offline",
        "functional-requirement",
        parent="goal-notes",
        verification=[{"command": "scripts/check_offline.sh"}],
    )
    result = compiled(tmp_path)
    # Its verification is the acceptance of its subtree: an evaluator above the work, never work.
    assert [t.node_id for t in result.tickets] == ["uc-edit"]
    assert result.containers == 1
    assert result.escalations == ()


def test_a_container_verification_reaches_its_use_cases_ticket_as_acceptance_to_not_break(
    tmp_path,
):
    write_sound_tree(tmp_path)
    write_node(
        tmp_path,
        "goal-notes",
        "goal",
        decisions=["dec-local-first"],
        verification=[{"command": "scripts/check_journey.sh", "expects": "the journey holds"}],
    )
    write_node(
        tmp_path,
        "fr-offline",
        "functional-requirement",
        parent="goal-notes",
        verification=[{"command": "scripts/check_offline.sh"}],
    )
    body = one_ticket(tmp_path, "uc-edit").body
    criteria = body.split("## Acceptance criteria\n")[1].split("\n\n## Stages")[0]
    assert criteria == "- `pytest tests/test_edit.py -q` exits 0: it persists"
    context = body.split("## Context\n")[1].split("\n\n## Not included")[0]
    assert "`scripts/check_offline.sh`" in context
    assert "`scripts/check_journey.sh` -- the journey holds" in context
    assert "must not break" in context


def test_a_goal_with_a_verification_is_still_never_a_ticket(tmp_path):
    write_sound_tree(tmp_path)
    write_node(
        tmp_path,
        "goal-notes",
        "goal",
        decisions=["dec-local-first"],
        verification=[{"command": "scripts/check_journey.sh"}],
    )
    result = compiled(tmp_path)
    assert [t.node_id for t in result.tickets] == ["uc-edit"]
    assert result.goals == 1
    assert result.escalations == ()


def test_a_leaf_requirement_without_a_verification_escalates(tmp_path):
    write_node(tmp_path, "goal-notes", "goal")
    write_node(tmp_path, "fr-lonely", "functional-requirement", parent="goal-notes")
    result = compiled(tmp_path)
    assert [e.node_id for e in result.escalations] == ["fr-lonely"]
    assert result.tickets == ()


def test_goals_and_nodes_past_pending_are_not_dispatched_by_this_step(tmp_path):
    write_sound_tree(tmp_path)
    write_node(
        tmp_path,
        "uc-live",
        "use-case",
        parent="fr-offline",
        state="improvised",
    )
    write_node(
        tmp_path,
        "uc-built",
        "use-case",
        parent="fr-offline",
        state="hardened",
        implementation="app/x.py",
        verification=[{"command": "true"}],
    )
    result = compiled(tmp_path)
    assert result.goals == 1
    assert result.past_pending == 2
    assert [t.node_id for t in result.tickets] == ["uc-edit"]
    assert result.escalations == ()


def test_a_pending_mechanism_that_a_spike_found_infeasible_escalates(tmp_path):
    write_sound_tree(tmp_path)
    write_node(
        tmp_path,
        "uc-edit",
        "use-case",
        parent="fr-offline",
        verification=[{"command": "true"}],
        spikes=[
            {
                "question": "can it run in the browser",
                "outcome": "infeasible",
                "finding": "no storage quota",
                "date": "2026-10-04",
            }
        ],
    )
    result = compiled(tmp_path)
    assert result.tickets == ()
    (escalation,) = result.escalations
    assert escalation.code == "mechanism-unresolvable"
    assert "no storage quota" in escalation.message


def test_an_infeasible_spike_does_not_stop_a_node_whose_mechanism_is_known(tmp_path):
    write_sound_tree(tmp_path)
    write_node(
        tmp_path,
        "uc-edit",
        "use-case",
        parent="fr-offline",
        mechanism="Use the file system instead",
        verification=[{"command": "true"}],
        spikes=[
            {
                "question": "can it run in the browser",
                "outcome": "infeasible",
                "finding": "no storage quota",
                "date": "2026-10-04",
            }
        ],
    )
    assert [t.node_id for t in compiled(tmp_path).tickets] == ["uc-edit"]


def test_a_feasible_or_inconclusive_spike_does_not_block_dispatch(tmp_path):
    write_sound_tree(tmp_path)
    write_node(
        tmp_path,
        "uc-edit",
        "use-case",
        parent="fr-offline",
        verification=[{"command": "true"}],
        spikes=[
            {"question": "q1", "outcome": "feasible", "finding": "f", "date": "2026-10-04"},
            {"question": "q2", "outcome": "inconclusive", "finding": "f", "date": "2026-10-04"},
        ],
    )
    assert [t.node_id for t in compiled(tmp_path).tickets] == ["uc-edit"]


def test_a_node_can_escalate_for_both_reasons(tmp_path):
    write_sound_tree(tmp_path)
    write_node(
        tmp_path,
        "uc-both",
        "use-case",
        parent="fr-offline",
        spikes=[{"question": "q", "outcome": "infeasible", "finding": "f", "date": "2026-10-04"}],
    )
    codes = sorted(e.code for e in compiled(tmp_path).escalations if e.node_id == "uc-both")
    assert codes == ["mechanism-unresolvable", "missing-verification"]


def test_foundation_nodes_come_first(tmp_path):
    write_sound_tree(tmp_path)
    write_node(
        tmp_path,
        "uc-aaa-persistence",
        "use-case",
        parent="fr-offline",
        verification=[{"command": "true"}],
    )
    write_node(
        tmp_path,
        "uc-zzz-persistence",
        "use-case",
        parent="fr-offline",
        foundation=True,
        verification=[{"command": "true"}],
    )
    assert [t.node_id for t in compiled(tmp_path).tickets] == [
        "uc-zzz-persistence",
        "uc-aaa-persistence",
        "uc-edit",
    ]


# --------------------------------------------------------------------------------------------
# Refusals
# --------------------------------------------------------------------------------------------


def test_a_tree_that_fails_the_doctor_compiles_nothing(tmp_path):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "uc-orphan", "use-case", parent="fr-gone")
    with pytest.raises(CompileError, match="fails the doctor") as raised:
        compiled(tmp_path)
    assert [d.code for d in raised.value.defects] == ["dangling-parent"]


def test_no_budget_class_is_an_error_and_never_a_guess(tmp_path):
    write_sound_tree(tmp_path)
    with pytest.raises(CompileError, match="no budget class"):
        compiled(tmp_path, budget_class="")


def test_an_unknown_budget_class_is_refused(tmp_path):
    write_sound_tree(tmp_path)
    with pytest.raises(CompileError, match="not a worker class"):
        compiled(tmp_path, budget_class="no-such-class")


def test_a_role_class_is_not_a_budget_class_for_a_ticket(tmp_path):
    write_sound_tree(tmp_path)
    with pytest.raises(CompileError, match="not a worker class"):
        compiled(tmp_path, budget_class="validator")


def test_a_config_whose_task_label_is_gone_refuses(tmp_path):
    write_sound_tree(tmp_path)
    config = load_agents_config(EXAMPLE_CONFIG)
    config.project.labels.types = ["epic", "bug"]
    with pytest.raises(CompileError, match="no 'task'"):
        compile_tree(load_tree(tmp_path), config, budget_class=BUDGET_CLASS, tree_root="product")


def test_compile_runs_no_subprocess_so_it_cannot_reach_gh_or_a_network(tmp_path, monkeypatch):
    write_sound_tree(tmp_path)

    def forbidden(*args, **kwargs):
        raise AssertionError(f"compile started a subprocess: {args}")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    assert [t.node_id for t in compiled(tmp_path).tickets] == ["uc-edit"]


# --------------------------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------------------------


def test_the_json_output_carries_every_ticket_and_escalation(tmp_path):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "uc-vague", "use-case", parent="fr-offline")
    data = json.loads(render_compile_json(compiled(tmp_path)))
    assert data == compile_as_data(compiled(tmp_path))
    assert data["summary"] == {
        "tickets": 1,
        "escalations": 1,
        "goals_skipped": 1,
        "containers_skipped": 1,
        "past_pending_skipped": 0,
    }
    (ticket,) = data["tickets"]
    assert set(ticket) == {"node", "path", "title", "labels", "budget_class", "body"}
    assert ticket["labels"] == ["type:task"]
    assert data["escalations"][0]["code"] == "missing-verification"


def test_the_text_output_separates_tickets_from_escalations(tmp_path):
    write_sound_tree(tmp_path)
    write_node(tmp_path, "uc-vague", "use-case", parent="fr-offline")
    text = render_compile_text(compiled(tmp_path))
    assert text.startswith("compiled 1 ticket(s), 1 escalation(s)")
    assert "=== ticket: uc-edit ===" in text
    assert "=== escalation: uc-vague ===" in text
    assert "product/uc-vague.md: missing-verification:" in text


def test_the_same_tree_compiles_to_the_same_bytes(tmp_path):
    write_sound_tree(tmp_path)
    assert render_compile_json(compiled(tmp_path)) == render_compile_json(compiled(tmp_path))


def test_files_hold_exactly_the_body_per_ticket_and_an_index(tmp_path):
    write_sound_tree(tmp_path)
    result = compiled(tmp_path)
    out_dir = tmp_path / "out" / "nested"
    written = write_compile_files(result, out_dir)
    assert sorted(path.name for path in written) == ["compile.json", "uc-edit.md"]
    assert (out_dir / "uc-edit.md").read_text() == result.tickets[0].body
    assert json.loads((out_dir / "compile.json").read_text()) == compile_as_data(result)
