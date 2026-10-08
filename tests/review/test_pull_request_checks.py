import argparse
from unittest.mock import patch

import pytest

from agent_os import issues
from agent_os.review.pull_request_checks import refusal_for_issue

GREEN = {"name": "tests", "status": "COMPLETED", "conclusion": "SUCCESS"}
RED = {"name": "tests", "status": "COMPLETED", "conclusion": "FAILURE"}
RUNNING = {"name": "lint", "status": "IN_PROGRESS", "conclusion": ""}


def pull_request(rollup, body="Closes #7", number=12):
    return {"number": number, "body": body, "statusCheckRollup": rollup}


def test_a_red_check_refuses_and_names_it():
    refusal = refusal_for_issue(7, [pull_request([GREEN, RED])])
    assert "#12" in refusal and "failing: tests" in refusal


def test_a_running_check_refuses_as_not_finished():
    assert "not finished: lint" in refusal_for_issue(7, [pull_request([GREEN, RUNNING])])


def test_a_legacy_commit_status_in_error_refuses():
    status = {"context": "ci/other", "state": "ERROR"}
    assert "failing: ci/other" in refusal_for_issue(7, [pull_request([status])])


def test_all_green_and_skipped_passes():
    skipped = {"name": "docs", "status": "COMPLETED", "conclusion": "SKIPPED"}
    assert refusal_for_issue(7, [pull_request([GREEN, skipped])]) is None


def test_an_issue_without_an_open_pull_request_is_not_gated():
    assert refusal_for_issue(7, [pull_request([RED], body="Closes #8")]) is None


@pytest.mark.parametrize("rollup, moves", [([RED], False), ([GREEN], True)])
def test_move_to_review_is_refused_while_the_pull_request_checks_are_red(rollup, moves):
    current = {"labels": [], "state": "OPEN", "title": "t", "html_url": "u"}
    with (
        patch.object(issues, "repo_name", return_value="owner/name"),
        patch.object(issues, "gh_json", return_value=[pull_request(rollup)]),
        patch.object(issues, "gh_json_dict", return_value=current),
        patch.object(issues, "label_exists", return_value=True),
        patch.object(issues, "update_issue") as update,
        patch.object(issues, "mirror_board_column", return_value="board:"),
        patch.object(issues, "page_review_ready", return_value="page"),
    ):
        command = argparse.Namespace(numbers=[7], state="review")
        if moves:
            issues.cmd_move(command)
            assert update.called
        else:
            with pytest.raises(SystemExit, match="refused.*failing: tests"):
                issues.cmd_move(command)
            assert not update.called
