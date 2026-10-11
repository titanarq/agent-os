"""The node of the commented page reaches the brief, and an item may leave `node` null (agent-os#185)."""

from __future__ import annotations

from agent_os.product.interpreter.brief import build_brief
from agent_os.product.interpreter.interpretation import parse_interpretation
from agent_os.product.interpreter.request import parse_request
from tests.product.puntal.interpreter.interpreter_support import item, model_answer, request_json

PAGE_NODE = {"id": "uc-see-an-ad", "title": "See one ad", "description": "The page of a single ad."}


def test_the_page_node_of_the_request_is_passed_to_the_brief_next_to_the_case():
    request = parse_request(request_json(page_node=PAGE_NODE), tree_root=None)
    brief = build_brief(request, max_thread_messages=40, rejection=None)
    assert "# Case\nid: uc-publish-an-ad" in brief
    assert "# Node of the page the owner is commenting on" in brief
    assert "id: uc-see-an-ad" in brief


def test_a_request_without_a_page_node_has_no_such_section():
    request = parse_request(request_json(), tree_root=None)
    assert request.page_node is None
    assert "commenting on" not in build_brief(request, max_thread_messages=40, rejection=None)


def test_an_envelope_with_a_null_node_is_a_valid_interpretation():
    request = parse_request(request_json(page_node=PAGE_NODE), tree_root=None)
    answer = model_answer(items=[item(node=None)])
    interpretation, problems = parse_interpretation(answer, request)
    assert not problems
    assert interpretation.items[0].node is None
