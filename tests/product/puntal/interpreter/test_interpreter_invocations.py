"""The recent answers of the puntal in the brief, and the code binding of what an item names and of
the `approved` of a verdict and a `puntal_change` (agent-os#180). Pieces only: no model runs."""

from __future__ import annotations

import json

import pytest

from agent_os.product.interpreter.brief import build_brief
from agent_os.product.interpreter.constants import MAX_INVOCATION_ANSWER_CHARS
from agent_os.product.interpreter.interpretation import parse_interpretation
from agent_os.product.interpreter.proposals.confirmation import Confirmation
from agent_os.product.interpreter.request import parse_request
from tests.product.puntal.interpreter.interpreter_support import item, model_answer, request_json

INVOCATIONS = [
    {"invocation_id": "inv-a", "action": "Resend notice", "page": "/ads/1", "answer": "x" * 2000},
    {
        "invocation_id": "inv-b",
        "action": "Close ad",
        "node": "uc-publish-an-ad",
        "answer": "Closed",
    },
]
LISTED = Confirmation((("uc-publish-an-ad", "Publish an ad"),))
QUESTION = "Shall I record it like this?"


def request_of(**fields):
    return parse_request(request_json(invocations=INVOCATIONS, **fields), tree_root=None)


def verdict(invocation="inv-b", **fields):
    return item(
        "verdict", "Reject the answer", verdict="reject", invocations=[invocation], **fields
    )


def interpret(*items, request=None, confirmation=None, needs_answer=False, reply="Understood."):
    answer = model_answer(reply=reply, items=list(items), needs_answer=needs_answer)
    return parse_interpretation(answer, request or request_of(), confirmation)


def test_the_brief_lists_each_carried_answer_by_id_cut_to_a_fixed_length():
    brief = build_brief(request_of(), max_thread_messages=40, rejection=None)
    assert "inv-a: the answer to «Resend notice» on page /ads/1" in brief
    assert "x" * MAX_INVOCATION_ANSWER_CHARS + "..." in brief
    assert "x" * (MAX_INVOCATION_ANSWER_CHARS + 1) not in brief


def test_the_brief_says_when_no_answer_is_carried():
    request = parse_request(request_json(), tree_root=None)
    assert "(none carried" in build_brief(request, max_thread_messages=40, rejection=None)


@pytest.mark.parametrize(
    "make", [verdict, lambda invocation: {**verdict(invocation), "kind": "change"}]
)
def test_an_item_naming_an_answer_the_request_did_not_carry_is_a_retry_reason(make):
    interpretation, problems = interpret(make("inv-zzz"))
    assert interpretation is None
    assert any("'inv-zzz'" in problem and "did not carry" in problem for problem in problems)


def test_a_verdict_on_a_carried_answer_is_accepted():
    interpretation, problems = interpret(verdict())
    assert problems == [] and interpretation.items[0].invocations == ("inv-b",)


def test_a_puntal_change_without_an_answer_is_a_retry_reason():
    interpretation, problems = interpret(item("puntal_change", "It ignored the case"))
    assert interpretation is None and any("puntal_change names" in p for p in problems)


def test_a_corrected_item_may_keep_an_answer_that_has_left_the_carried_window():
    held = {**verdict("inv-old"), "id": "item-1"}
    request = request_of(items=[held])
    interpretation, problems = interpret({**held, "note": "still wrong"}, request=request)
    assert problems == [] and interpretation.items[0].invocations == ("inv-old",)


@pytest.mark.parametrize("confirmation", [None, LISTED])
def test_a_puntal_change_is_never_born_approved_with_the_key_off_or_on(confirmation):
    new = item("puntal_change", "It ignored the case", invocations=["inv-a"], status="approved")
    interpretation, problems = interpret(
        new, confirmation=confirmation, needs_answer=True, reply=f"Review the puntal? {QUESTION}"
    )
    assert interpretation is None and any("new in this turn" in problem for problem in problems)


def test_with_the_key_off_a_verdict_is_born_approved_and_a_puntal_change_proposed():
    interpretation, problems = interpret(
        verdict(), item("puntal_change", "It ignored the case", invocations=["inv-a"])
    )
    assert problems == []
    assert [i.status for i in interpretation.items] == ["approved", "proposed"]


def test_with_the_key_on_a_verdict_is_proposed_and_approved_only_on_the_same_item_after_the_yes():
    reply = f"Publish an ad, /ads/new: reject that answer. {QUESTION}"
    interpretation, _ = interpret(verdict(), confirmation=LISTED, needs_answer=True, reply=reply)
    assert interpretation.items[0].status == "proposed"
    shown = {**json.loads(json.dumps(interpretation.items[0].as_json())), "id": "item-1"}
    request = request_of(items=[shown])
    again = {**shown, "status": "approved", "id": "item-1"}
    approved, problems = interpret(again, request=request, confirmation=LISTED)
    assert problems == [] and approved.items[0].status == "approved"
    changed = {**again, "invocations": ["inv-a"]}
    refused, problems = interpret(changed, request=request, confirmation=LISTED)
    assert refused is None and any("invocation changed" in problem for problem in problems)
