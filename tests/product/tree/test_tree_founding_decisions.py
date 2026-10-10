"""The six founding decisions of `docs/AGENTOS_V2_PLAN.md` as the first real ledger entries.

The plan says: if the format cannot hold them, the format is wrong. So Agentos's own tree under
`docs/tree/` is run through the same doctor and the same slicing every host's tree is, and it
is held to the plan's own table: nothing added, nothing dropped, nothing invented. A change to one
of these files that breaks the format fails this file, the way a host literal fails
`tests/test_no_host_literals.py`.

Pure filesystem; the ledger is copied under `tmp_path` wherever a test changes it.
"""

from __future__ import annotations

import pathlib
import re
import shutil

import pytest
from tree_helpers import write_node

from agent_os.cli import AGENT_OS_DIR
from agent_os.product.tree.checks import check_tree
from agent_os.product.tree.cli import format_defect
from agent_os.product.tree.loader import load_tree
from agent_os.product.tree.slicing import SliceError, build_slice, render_slice_markdown

LEDGER = AGENT_OS_DIR / "docs" / "tree"
PLAN = AGENT_OS_DIR / "docs" / "AGENTOS_V2_PLAN.md"

SEED_BY_ROW = {
    1: "dec-v2-wraps-v1",
    2: "dec-tree-as-repo-files",
    3: "dec-usage-telemetry-from-one-real-human",
    4: "dec-state-real-behavior-improvisable",
    5: "dec-obey-while-challenging",
    6: "dec-puntales-run-as-headless-processes",
}


def plan_rows() -> dict[int, tuple[str, str, str]]:
    """The rows of the plan's 'Founding decisions' table: number -> (decision, premises, trigger)."""
    text = PLAN.read_text()
    rows = re.findall(r"^\| (\d+) \| (.+?) \| (.+?) \| (.+?) \|$", text, flags=re.MULTILINE)
    assert rows, "the plan's founding-decisions table was not found"
    return {
        int(number): (decision, premises, trigger) for number, decision, premises, trigger in rows
    }


def copy_of_the_ledger(tmp_path: pathlib.Path) -> pathlib.Path:
    copy = tmp_path / "ledger"
    shutil.copytree(LEDGER, copy)
    return copy


def test_the_ledger_passes_the_tree_doctor():
    defects = check_tree(load_tree(LEDGER))
    assert defects == [], "\n".join(format_defect(defect) for defect in defects)


GOALS = (
    "goal-product-early-grown-by-use",
    "goal-faithful-to-the-owners-goals",
    "goal-owner-decides-what-agentos-decides-how",
    "goal-improves-with-every-product",
)

# Added on the owner's word of 2026-10-09 (a global goal of efficiency linked to self-improvement),
# after the four founding goals; its evaluators are a proposal that waits for the owner's signature,
# so it does not share the founding goals' "set by the owner on 2026-10-06" closing line.
EFFICIENCY_GOAL = "goal-efficient-with-what-it-spends"


@pytest.mark.parametrize("goal_id", GOALS)
def test_each_goal_carries_its_evaluators_in_the_verification_field_as_judged_criteria(goal_id):
    goal = load_tree(LEDGER).nodes[goal_id]
    assert goal.verification, goal_id
    assert all(check.is_judged for check in goal.verification), goal_id
    assert "Evaluators (set by the owner" not in goal.description
    assert not [line for line in goal.description.splitlines() if line.startswith("- ")]
    assert goal.description.splitlines()[-1] == (
        "Evaluators: in `verification`, set by the owner on 2026-10-06 -- trends until the "
        "vector gives the first measurements, numeric thresholds after."
    )


def test_the_evaluators_are_moved_verbatim_and_none_is_dropped():
    expected = {
        "goal-product-early-grown-by-use": [
            "Time from the owner writing a product's goals to a first usable product: short.",
            "Share of use served by consolidated parts: grows.",
            "Defects found after a part is consolidated: few.",
        ],
        "goal-faithful-to-the-owners-goals": [
            "The tests of the product's own goals pass.",
            "Unverified exposure per branch: low.",
            "Rework decays over time.",
            "Work lost when a step is undone: at most one step.",
        ],
        "goal-owner-decides-what-agentos-decides-how": [
            "Doubts about how that reach the owner: none.",
            "Questions and owner time per session: do not grow.",
            "Judgments Agentos takes alone with its accuracy held: grow.",
            "Owner reversals: few.",
        ],
        "goal-improves-with-every-product": [
            "Recurrence of failures already recorded: tends to zero.",
            "Cost per verified checkpoint: falls from one method version to the next.",
            "Share of new nodes that reuse existing components: grows.",
            "Once a second product exists: it costs less than the first.",
        ],
    }
    tree = load_tree(LEDGER)
    assert set(expected) == set(GOALS)
    for goal_id, criteria in expected.items():
        assert [check.judge for check in tree.nodes[goal_id].verification] == criteria


def test_parallelism_is_a_requirement_under_the_first_goal_with_the_owners_four_evaluators():
    # The owner, 2026-10-09: parallelising is a requirement under the first goal, not a fifth goal,
    # with these evaluators approved as trends.
    tree = load_tree(LEDGER)
    requirement = tree.nodes["fr-independent-work-runs-in-parallel"]
    assert requirement.type == "functional-requirement"
    assert requirement.parent == "goal-product-early-grown-by-use"
    assert "dec-dispatch-never-runs-two-tickets-on-the-same-code" in requirement.decisions
    assert all(check.is_judged for check in requirement.verification)
    assert [check.judge for check in requirement.verification] == [
        "Work items running at once when there is independent work: grows.",
        "A wave's wall-clock time approaches that of its longest ticket, not the sum of its tickets.",
        "Merge conflicts between work done in parallel: few.",
        "No dispatchable work waits for another run to finish without a reason.",
    ]
    assert "Owner, 2026-10-09" in requirement.sources[0]
    goal_ids = {node.id for node in tree.nodes.values() if node.type == "goal"}
    assert goal_ids == {*GOALS, EFFICIENCY_GOAL}


def test_the_efficiency_goal_and_the_self_improvement_goal_name_each_other():
    tree = load_tree(LEDGER)
    efficiency, improvement = (
        tree.nodes[EFFICIENCY_GOAL],
        tree.nodes["goal-improves-with-every-product"],
    )
    assert "goal-improves-with-every-product" in efficiency.description
    assert EFFICIENCY_GOAL in improvement.description
    assert efficiency.verification and all(check.is_judged for check in efficiency.verification)
    assert "until the owner signs them" in efficiency.description


def test_the_slice_of_a_use_case_of_agentos_shows_its_goals_evaluators_as_judged():
    cut = build_slice(load_tree(LEDGER), "uc-use-the-product-from-early-on")
    assert cut.ancestors[-1].id == "goal-product-early-grown-by-use"
    text = render_slice_markdown(cut)
    assert "- judged by an agent: Share of use served by consolidated parts: grows." in text


def test_the_decisions_from_the_plans_table_are_exactly_its_six_rows():
    # The tree also holds Agentos's own goals and later decisions; the seeds are the entries whose
    # source is the plan's table, and of those there are exactly six.
    tree = load_tree(LEDGER)
    from_the_table = [
        decision_id
        for decision_id, decision in tree.decisions.items()
        if "'Founding decisions' row" in decision.sources[0]
    ]
    assert sorted(from_the_table) == sorted(SEED_BY_ROW.values())
    assert sorted(plan_rows()) == [1, 2, 3, 4, 5, 6]


@pytest.mark.parametrize("row", sorted(SEED_BY_ROW))
def test_each_seed_is_its_table_row_and_adds_nothing_to_it(row):
    decision = load_tree(LEDGER).decisions[SEED_BY_ROW[row]]
    table_decision, table_premises, table_trigger = plan_rows()[row]
    assert decision.title == table_decision
    for premise in decision.premises:
        assert premise.lower() in table_premises.lower(), premise
    for trigger in decision.review_triggers:
        assert trigger.lower() in table_trigger.lower(), trigger
    assert f"'Founding decisions' row {row}" in decision.sources[0]
    assert "2026-10-04" in decision.sources[0]


@pytest.mark.parametrize("row", sorted(SEED_BY_ROW))
def test_each_seed_carries_what_a_decision_must(row):
    decision = load_tree(LEDGER).decisions[SEED_BY_ROW[row]]
    assert decision.state == "in-force"
    assert decision.decided.isoformat() == "2026-10-04"
    assert decision.premises and decision.review_triggers and decision.rejected_alternatives
    assert decision.superseded_by is None and decision.friction == []


def test_the_seeds_triggers_are_not_dropped_from_the_plans_table():
    # "A, or B" in a table cell is two triggers in the ledger: every `or` of a cell is an entry.
    tree = load_tree(LEDGER)
    for row, (_decision, _premises, trigger) in plan_rows().items():
        expected = len(re.split(r",? or ", trigger))
        assert len(tree.decisions[SEED_BY_ROW[row]].review_triggers) == expected, row


def test_an_implied_alternative_says_so_in_its_text_and_a_stated_one_is_not_so_marked():
    for decision in load_tree(LEDGER).decisions.values():
        for alternative in decision.rejected_alternatives:
            says_so = "not argued at approval" in alternative.reason
            assert says_so == (alternative.basis == "implied"), (decision.id, alternative.option)


def test_the_slice_of_a_node_under_the_founding_decisions_carries_them(tmp_path):
    ledger = copy_of_the_ledger(tmp_path)
    write_node(
        ledger,
        "goal-lighthouse",
        "goal",
        decisions=["dec-obey-while-challenging", "dec-tree-as-repo-files"],
    )
    write_node(
        ledger,
        "fr-shell",
        "functional-requirement",
        parent="goal-lighthouse",
        decisions=["dec-state-real-behavior-improvisable"],
    )
    write_node(ledger, "uc-open-note", "use-case", parent="fr-shell")
    tree = load_tree(ledger)
    assert check_tree(tree) == []
    text = render_slice_markdown(build_slice(tree, "uc-open-note"))
    decisions = text.split("## Decisions in force")[1]
    assert decisions.index("`dec-state-real-behavior-improvisable`") < decisions.index(
        "`dec-obey-while-challenging`"
    )
    for decision_id in (
        "dec-state-real-behavior-improvisable",
        "dec-obey-while-challenging",
        "dec-tree-as-repo-files",
    ):
        assert f"`{decision_id}`" in decisions
    # Decisions nobody on the chain points at stay out, however true they are.
    assert "dec-v2-wraps-v1" not in text
    assert "dec-usage-telemetry-from-one-real-human" not in text
    assert "dec-puntales-run-as-headless-processes" not in text
    assert "Parallel workers relitigating decisions never converge" in decisions
    assert "Challenge channel unused after 2 months" in decisions
    assert "(implied, not argued at approval)" in decisions


def test_a_seed_under_review_is_labelled_still_obeyed_in_the_slice(tmp_path):
    ledger = copy_of_the_ledger(tmp_path)
    challenged = ledger / "dec-obey-while-challenging.md"
    challenged.write_text(challenged.read_text().replace("state: in-force", "state: under-review"))
    write_node(ledger, "goal-lighthouse", "goal", decisions=["dec-obey-while-challenging"])
    text = render_slice_markdown(build_slice(load_tree(ledger), "goal-lighthouse"))
    assert "UNDER REVIEW -- still obeyed while it is challenged" in text


def test_a_seed_can_be_superseded_by_another_and_a_node_must_then_follow(tmp_path):
    ledger = copy_of_the_ledger(tmp_path)
    old = ledger / "dec-usage-telemetry-from-one-real-human.md"
    old.write_text(
        old.read_text()
        .replace("state: in-force", "state: superseded")
        .replace("review_triggers:", "superseded_by: dec-v2-wraps-v1\nreview_triggers:", 1)
    )
    write_node(
        ledger, "goal-lighthouse", "goal", decisions=["dec-usage-telemetry-from-one-real-human"]
    )
    tree = load_tree(ledger)
    assert [d.code for d in check_tree(tree)] == ["superseded-decision-in-use"]
    with pytest.raises(SliceError):
        build_slice(tree, "goal-lighthouse")
    write_node(ledger, "goal-lighthouse", "goal", decisions=["dec-v2-wraps-v1"])
    assert check_tree(load_tree(ledger)) == []


def test_friction_can_accumulate_against_a_seed_and_the_slice_counts_it(tmp_path):
    ledger = copy_of_the_ledger(tmp_path)
    write_node(ledger, "goal-lighthouse", "goal", decisions=["dec-obey-while-challenging"])
    write_node(ledger, "fr-shell", "functional-requirement", parent="goal-lighthouse")
    seed = ledger / "dec-obey-while-challenging.md"
    friction = (
        "friction:\n"
        "  - date: 2026-10-05\n    summary: the constraint made a solution worse\n"
        "    node: fr-shell\n    evidence: validator review\n"
        "  - date: 2026-10-06\n    summary: again\n"
    )
    seed.write_text(seed.read_text().replace("\n---\n", f"\n{friction}---\n", 1))
    tree = load_tree(ledger)
    assert check_tree(tree) == []
    assert len(tree.decisions["dec-obey-while-challenging"].friction) == 2
    text = render_slice_markdown(build_slice(tree, "fr-shell"))
    assert "Friction entries logged against it: 2" in text
