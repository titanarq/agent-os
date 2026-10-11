"""`sessions.confirm_before_dispatch` on: a change is proposed to the owner and the owner's answer is
bound by code. The fake `claude` plays the model; nothing here reaches a real backend."""

from __future__ import annotations

import json

from agent_os.cli import AGENT_OS_DIR
from tests.product.puntal.interpreter.interpreter_support import (  # noqa: F401 -- the fixture
    EXAMPLE_CONFIG,
    interpret,
    interpreter_environment,
    item,
    model_answer,
    play_answers,
    request_json,
)

TREE = str(AGENT_OS_DIR / "docs" / "tree")
OTHER_USE_CASE = "uc-open-a-test-session-for-a-branch"
PROPOSAL = (
    "I would ask for: label the checkbox (case Publish an ad, page /ads/new). Each worker gets your "
    "words and the case description; the rest is left out. Shall I launch it like this?"
)
PROPOSED = {"status": "proposed"}


def run(environment, tmp_path, *answers, **request):
    environment["AGENTS_CONFIG_PATH"] = str(EXAMPLE_CONFIG)
    play_answers(tmp_path, environment, *answers)
    completed = interpret(environment, request_json(**request), "--tree-root", TREE)
    return completed, json.loads(completed.stdout)


def proposal(**overrides) -> str:
    return model_answer(reply=PROPOSAL, needs_answer=True, items=[item()], **overrides)


def carried(**fields) -> dict:
    return {**item(**PROPOSED), "id": "item-1", **fields}


THREAD = [{"role": "owner", "text": "first"}, {"role": "agent", "text": PROPOSAL}]
ANSWER = {"text": "yes, launch it", "case": "uc-publish-an-ad", "page": "/ads/new"}


def test_a_new_change_is_born_proposed_whatever_the_model_wrote_and_a_decision_has_no_status(
    tmp_path, environment
):
    items = [item(status="proposed"), item("decision", "Drop the warning", status="proposed")]
    completed, envelope = run(
        environment, tmp_path, model_answer(reply=PROPOSAL, needs_answer=True, items=items)
    )
    assert completed.returncode == 0, completed.stderr
    assert [i.get("status") for i in envelope["items"]] == ["proposed", None]


def test_approved_on_a_new_item_is_a_retry_reason_not_a_silent_downgrade(tmp_path, environment):
    first = model_answer(reply="Done, launched.", items=[item(status="approved")])
    _, envelope = run(environment, tmp_path, first, proposal())
    assert envelope["retries"] == 1 and envelope["items"][0]["status"] == "proposed"
    assert "new in this turn" in (tmp_path / "argv.log").read_text()


def test_approved_on_a_changed_or_non_change_item_is_a_retry_reason(tmp_path, environment):
    changed = {**item(status="approved", summary="Another thing"), "id": "item-1"}
    decision = {**item("decision", status="approved"), "id": "item-2"}
    known = [carried(), {**item("decision"), "id": "item-2"}]
    for returned in (changed, decision):
        completed, envelope = run(
            environment,
            tmp_path,
            model_answer(items=[returned]),
            "not json",
            thread=THREAD,
            items=known,
            message=ANSWER,
        )
        assert completed.returncode == 5 and envelope["retries"] == 1


def test_an_approval_on_the_carried_unchanged_item_is_kept(tmp_path, environment):
    answer = model_answer(reply="Launching.", items=[{**item(status="approved"), "id": "item-1"}])
    completed, envelope = run(
        environment, tmp_path, answer, thread=THREAD, items=[carried()], message=ANSWER
    )
    assert completed.returncode == 0, completed.stderr
    assert envelope["items"][0]["status"] == "approved" and envelope["needs_answer"] is False


def test_a_correction_returns_to_proposed(tmp_path, environment):
    corrected = {**item(summary="Label it and make it bigger"), "id": "item-1"}
    answer = model_answer(reply=PROPOSAL, needs_answer=True, items=[corrected])
    completed, envelope = run(
        environment,
        tmp_path,
        answer,
        thread=THREAD,
        items=[carried(status="approved")],
        message=ANSWER,
    )
    assert completed.returncode == 0, completed.stderr
    assert envelope["items"][0]["status"] == "proposed"


def test_a_node_the_brief_does_not_list_is_a_retry_reason_and_a_listed_one_is_accepted(
    tmp_path, environment
):
    unknown = model_answer(
        reply=PROPOSAL, needs_answer=True, items=[item(node="uc-nothing-like-it")]
    )
    completed, envelope = run(environment, tmp_path, unknown, proposal())
    assert envelope["retries"] == 1
    assert "uc-nothing-like-it" in (tmp_path / "argv.log").read_text()
    listed = model_answer(
        reply=PROPOSAL.replace("Publish an ad", "Open a test session from the app"),
        needs_answer=True,
        items=[item(node=OTHER_USE_CASE)],
    )
    completed, envelope = run(environment, tmp_path, listed)
    assert completed.returncode == 0 and envelope["retries"] == 0, completed.stderr


def test_a_proposal_that_is_not_a_question_or_omits_the_case_or_the_page_is_retried(
    tmp_path, environment
):
    no_flag = model_answer(reply=PROPOSAL, items=[item()])
    no_case = model_answer(reply="Label it on /ads/new? ", needs_answer=True, items=[item()])
    no_page = model_answer(reply="Label it, case Publish an ad?", needs_answer=True, items=[item()])
    for number, bad in enumerate((no_flag, no_case, no_page)):
        playbook_dir = tmp_path / f"round-{number}"
        playbook_dir.mkdir()
        _, envelope = run(environment, playbook_dir, bad, proposal())
        assert envelope["retries"] == 1 and envelope["outcome"] == "ok"


def test_the_reply_may_grow_by_a_constant_per_proposed_change(tmp_path, environment):
    long_reply = PROPOSAL + " " + "x" * 1200
    _, envelope = run(
        environment, tmp_path, model_answer(reply=long_reply, needs_answer=True, items=[item()])
    )
    assert envelope["retries"] == 0 and len(envelope["reply"]) > 1200


def test_dry_run_shows_the_proposal_rules_and_the_use_case_listing(tmp_path, environment):
    environment["AGENTS_CONFIG_PATH"] = str(EXAMPLE_CONFIG)
    completed = interpret(environment, request_json(), "--tree-root", TREE, "--dry-run")
    assert completed.returncode == 0, completed.stderr
    assert "PROPOSING EVERY CHANGE TO THE OWNER" in completed.stdout
    assert "- uc-publish-an-ad: Publish an ad\n" in completed.stdout
    assert f"- {OTHER_USE_CASE}: " in completed.stdout


def test_with_the_key_off_the_prompt_and_the_brief_carry_no_confirmation_rule(
    tmp_path, environment
):
    completed = interpret(environment, request_json(), "--dry-run")
    assert "PROPOSING EVERY CHANGE" not in completed.stdout
    assert "Use cases of the tree" not in completed.stdout
