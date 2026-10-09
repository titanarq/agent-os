"""The pure half of `resume --rework`: which review is owed, and the stage that carries it."""

from __future__ import annotations

import pytest

from agent_os.product.tracker.rework import (
    ReworkRefused,
    newest_review_requesting_changes,
    prepare,
    rework_stage_title,
    with_stage_appended,
)

BRANCH = "claude/347-staged"
BODY = "## Goal\nx\n\n## Stages\n- [x] Write the test\n- [x] Make it pass\n\n## Acceptance\ny\n"


def _review(state, body="fix the naming"):
    return {"state": state, "body": body}


def _pull_request(*reviews, number=42):
    return {"number": number, "reviews": list(reviews)}


def test_the_newest_settling_review_is_the_one_that_counts():
    pull_request = _pull_request(
        _review("CHANGES_REQUESTED", "old"),
        _review("COMMENTED"),
        _review("CHANGES_REQUESTED", "new"),
    )
    number, review = newest_review_requesting_changes([pull_request], BRANCH)
    assert (number, review["body"]) == (42, "new")


@pytest.mark.parametrize(
    "pull_requests, reason",
    [
        ([], "no open pull request"),
        ([_pull_request()], "no review"),
        ([_pull_request(_review("COMMENTED"))], "no review"),
        ([_pull_request(_review("CHANGES_REQUESTED"), _review("APPROVED"))], "is APPROVED"),
        ([_pull_request(_review("CHANGES_REQUESTED"), _review("DISMISSED"))], "is DISMISSED"),
    ],
)
def test_a_pull_request_that_owes_no_changes_is_refused(pull_requests, reason):
    with pytest.raises(ReworkRefused, match=reason):
        newest_review_requesting_changes(pull_requests, BRANCH)


def test_the_stage_lands_at_the_end_of_the_stages_section_and_nowhere_else():
    updated = with_stage_appended(BODY, "Address the changes requested on PR #42")
    assert (
        "- [x] Make it pass\n- [ ] Address the changes requested on PR #42\n\n## Acceptance"
        in updated
    )
    assert updated.count("- [ ]") == 1


def test_a_second_round_on_the_same_pull_request_gets_its_own_title():
    first = rework_stage_title(42, ["Write the test"])
    second = rework_stage_title(42, ["Write the test", first])
    third = rework_stage_title(42, ["Write the test", first, second])
    assert first == "Address the changes requested on PR #42"
    assert (second, third) == (f"{first} (round 2)", f"{first} (round 3)")


def test_prepare_appends_a_stage_when_every_stage_is_committed():
    body, stage, context = prepare(
        [_pull_request(_review("CHANGES_REQUESTED", "rename x to y"))],
        BODY,
        branch=BRANCH,
        stages_done=2,
        stages_total=2,
    )
    assert stage == "Address the changes requested on PR #42"
    assert body is not None and f"- [ ] {stage}" in body
    assert "rename x to y" in context and "#42" in context


def test_prepare_does_not_append_twice_while_the_rework_stage_is_still_pending():
    planned = with_stage_appended(BODY, "Address the changes requested on PR #42")
    body, stage, _context = prepare(
        [_pull_request(_review("CHANGES_REQUESTED"))],
        planned,
        branch=BRANCH,
        stages_done=2,
        stages_total=3,
    )
    assert body is None
    assert stage == "Address the changes requested on PR #42"


def test_a_review_without_text_points_at_its_inline_comments():
    _body, _stage, context = prepare(
        [_pull_request(_review("CHANGES_REQUESTED", ""))],
        BODY,
        branch=BRANCH,
        stages_done=2,
        stages_total=2,
    )
    assert "gh pr view 42 --comments" in context


def test_an_unstaged_issue_has_no_plan_to_extend():
    with pytest.raises(ReworkRefused, match="no `## Stages`"):
        prepare(
            [_pull_request(_review("CHANGES_REQUESTED"))],
            "## Goal\nx\n",
            branch=BRANCH,
            stages_done=0,
            stages_total=0,
        )
