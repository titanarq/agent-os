"""What a branch of the tree shows on the board: pure functions of a loaded tree."""

from __future__ import annotations

from board_helpers import write_board_tree

from agent_os.product.board.branches import (
    branch_progress_summary,
    build_branches,
    render_branch_body,
)
from agent_os.product.tree.loader import load_tree


def branches_of(tmp_path):
    write_board_tree(tmp_path)
    return {branch.requirement_id: branch for branch in build_branches(load_tree(tmp_path))}


def test_a_branch_is_a_requirement_and_its_parts_are_its_use_cases(tmp_path):
    branches = branches_of(tmp_path)
    assert sorted(branches) == ["fr-offline", "fr-sync"]
    assert [part.node_id for part in branches["fr-offline"].parts] == [
        "uc-edit",
        "uc-export",
        "uc-search",
    ]


def test_a_requirement_without_use_cases_is_its_own_single_part(tmp_path):
    branches = branches_of(tmp_path)
    assert [(part.node_id, part.state) for part in branches["fr-sync"].parts] == [
        ("fr-sync", "implemented")
    ]


def test_the_progress_summary_counts_parts_by_state(tmp_path):
    summary = branch_progress_summary(branches_of(tmp_path)["fr-offline"])
    assert summary == "pending 1 | improvised 1 | implemented 0 | hardened 1"


def test_the_body_lists_open_what_questions_and_challenges(tmp_path):
    body = render_branch_body(branches_of(tmp_path)["fr-offline"])
    assert body.startswith("<!-- agent-os-board: fr-offline -->")
    assert "Should search cover archived notes?" in body
    assert "default answer: No" in body
    assert "no-solution" in body and "no format keeps the layout" in body


def test_the_body_is_identical_on_every_render(tmp_path):
    branch = branches_of(tmp_path)["fr-offline"]
    assert render_branch_body(branch) == render_branch_body(branch)
