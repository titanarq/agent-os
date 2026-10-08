"""What a worker is told about the `Node-Change` value of the commits it makes, and what the
validator is told to do when one carries the owner's word.

`owner` is the owner's own word. A worker that touched its node at the end of a ticket wrote it,
which made the history of the tree say the owner had asked for a change nobody had asked for.
"""

from __future__ import annotations

from agent_os.lib import prompt_substitutions, render_prompt


def rendered(role):
    values = prompt_substitutions()
    values.update(
        WORKTREE="/a/worktree", MAIN_CHECKOUT="/a/checkout", REVIEW_BACKEND_LINE="a review line"
    )
    return " ".join(render_prompt(role, values).split())


def test_the_worker_is_given_usage_and_rework_and_told_never_to_write_owner():
    rules = rendered("worker")
    assert "You are an agent, so two values are yours" in rules
    assert (
        "`usage` when you build, `rework` when you correct a rejection, and never `owner`" in rules
    )
    assert "You NEVER write it" in rules
    assert (
        "`open-pr` refuses a branch with an agent's commit that carries `Node-Change: owner`"
        in rules
    )


def test_the_worker_prompt_no_longer_offers_owner_as_a_value_the_issue_can_license():
    assert "the issue or the owner's comment says so, and you can cite it" not in rendered("worker")


def test_the_validator_requests_changes_on_the_owner_word_and_runs_the_deterministic_check():
    rules = rendered("validator")
    assert "NEVER `owner`" in rules
    assert "is a request for changes, whatever the issue quotes" in rules
    assert "--agent-authored" in rules
    assert f'--root "$PWD/{prompt_substitutions()["TREE_ROOT"]}"' in rules
