"""The open question of what in the chat, bound by code (agent-os#181). Pieces only: no model runs."""

from __future__ import annotations

import json

import pytest

from agent_os.product.interpreter.brief import build_brief
from agent_os.product.interpreter.constants import InterpreterRefused
from agent_os.product.interpreter.interpretation import parse_interpretation
from agent_os.product.interpreter.request import parse_request
from tests.product.puntal.interpreter.interpreter_support import (
    CASE,
    OWNER_MESSAGE,
    item,
    model_answer,
    request_json,
)

QUESTION = {"node": "uc-publish-an-ad", "question": "Is there a cap?", "default_answer": "No cap."}
OWNER_WORDS = "Yes, up to ten photos."


def answer_item(**fields):
    return item(
        "answer", "Photo cap", question="whatever", answer_text="whatever", node="other", **fields
    )


def pending_request(message=OWNER_WORDS):
    return parse_request(
        request_json(message={**OWNER_MESSAGE, "text": message}, pending_question=QUESTION),
        tree_root=None,
    )


def ask_request(**fields):
    document = json.loads(request_json(ask=QUESTION, **fields))
    del document["message"]
    return parse_request(json.dumps(document), tree_root=None)


def test_an_ask_request_needs_no_message_and_shows_the_question_in_the_brief():
    request = ask_request()
    assert request.message is None
    brief = build_brief(request, max_thread_messages=40, rejection=None)
    assert "Put this open question to the owner" in brief and "default answer: No cap." in brief
    assert "The owner's new message" not in brief


def test_an_ask_request_that_also_carries_a_message_is_refused():
    with pytest.raises(InterpreterRefused, match="carries no `message`"):
        parse_request(request_json(ask=QUESTION), tree_root=None)


def test_an_ask_request_while_a_proposal_waits_is_refused():
    waiting = item(status="proposed", id="item-1")
    with pytest.raises(InterpreterRefused, match="a proposal waits"):
        ask_request(items=[waiting])


def test_an_ask_turn_records_nothing_and_waits_for_the_owner():
    request = ask_request()
    said = model_answer(
        reply="Is there a cap? If you do not say, no cap stands.", needs_answer=True
    )
    interpretation, problems = parse_interpretation(said, request)
    assert problems == [] and interpretation.needs_answer and interpretation.items == ()
    _, problems = parse_interpretation(
        model_answer(reply="Is there a cap?", needs_answer=True, items=[item()]), request
    )
    assert any("`items` must be empty" in problem for problem in problems)
    _, problems = parse_interpretation(model_answer(reply="Noted."), request)
    assert any("`needs_answer` must be true" in problem for problem in problems)


def test_an_answer_stores_the_owners_message_verbatim_bound_to_the_carried_question():
    interpretation, problems = parse_interpretation(
        model_answer(items=[answer_item()]), pending_request()
    )
    assert problems == []
    (stored,) = interpretation.items
    assert (stored.node, stored.question, stored.answer_text) == (
        QUESTION["node"],
        QUESTION["question"],
        OWNER_WORDS,
    )


def test_an_explicit_yes_to_the_default_stores_the_defaults_text():
    said = model_answer(items=[answer_item() | {"answer_text": "No cap."}])
    interpretation, problems = parse_interpretation(said, pending_request("Yes, that is fine."))
    assert problems == [] and interpretation.items[0].answer_text == "No cap."


def test_an_answer_without_a_pending_question_or_twice_is_refused():
    _, problems = parse_interpretation(
        model_answer(items=[answer_item()]),
        parse_request(request_json(), tree_root=None),
    )
    assert any("needs a `pending_question`" in problem for problem in problems)
    _, problems = parse_interpretation(
        model_answer(items=[answer_item(), answer_item()]), pending_request()
    )
    assert any("ONE `answer` item" in problem for problem in problems)


def test_a_message_that_does_not_answer_is_read_as_any_other():
    interpretation, problems = parse_interpretation(model_answer(items=[item()]), pending_request())
    assert problems == [] and interpretation.items[0].kind == "change"
    assert CASE["id"] == interpretation.items[0].node
