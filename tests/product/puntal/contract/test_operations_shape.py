"""The shape of what a puntal returns in its one turn -- operations and answer -- and the validation
that sends a bad plan back for one more turn.

Pure functions. This file must not request the `engine` or `db_sandbox` fixture.
"""

from __future__ import annotations

import json

import pytest

from agent_os.product.puntal.fast.operations import (
    fill_bindings,
    parse_plan,
    render_answer,
    validate_plan,
)

VALID = {
    "operations": [
        {"op": "allocate", "counter": "ticket", "bind": "n"},
        {
            "op": "put",
            "collection": "tickets",
            "id": "T-{{n}}",
            "document": {"id": "T-{{n}}", "status": "open"},
        },
        {"op": "update", "collection": "tickets", "id": "T-1", "changes": {"status": "closed"}},
        {"op": "delete", "collection": "tickets", "id": "T-2"},
    ],
    "answer": {"ok": True, "ticket_id": "T-{{n}}"},
}


def parsed(value) -> object:
    plan, errors = parse_plan(value if isinstance(value, str) else json.dumps(value))
    assert plan is not None, errors
    return plan


def test_a_well_formed_plan_has_no_errors():
    assert validate_plan(parsed(VALID)) == []


def test_a_read_only_action_is_a_plan_with_no_operations():
    assert validate_plan(parsed({"operations": [], "answer": "the board is empty"})) == []


def test_the_plan_may_sit_inside_a_markdown_fence_and_carry_a_gap_note():
    text = '```json\n{"operations": [], "answer": "x", "gap": "asked for a CSV"}\n```'
    plan = parsed(text)
    assert plan.gap == "asked for a CSV" and validate_plan(plan) == []


def test_a_response_that_is_not_a_json_object_is_reported_not_raised():
    for text in ("", "sure, done", "[1, 2]", '{"operations": [}'):
        plan, errors = parse_plan(text)
        assert plan is None and errors and "JSON object" in errors[0]


@pytest.mark.parametrize(
    ("plan", "message"),
    [
        ({"operations": []}, "answer"),
        ({"answer": "x"}, "operations"),
        ({"operations": {}, "answer": "x"}, "operations"),
        ({"operations": [], "answer": "x", "explanation": "..."}, "explanation"),
        ({"operations": ["put"], "answer": "x"}, "operation 1"),
        ({"operations": [{"op": "upsert"}], "answer": "x"}, "upsert"),
        (
            {"operations": [{"op": "put", "collection": "c", "id": "i"}], "answer": "x"},
            "document",
        ),
        (
            {
                "operations": [
                    {"op": "put", "collection": "c", "id": "i", "document": {}, "extra": 1}
                ],
                "answer": "x",
            },
            "extra",
        ),
        (
            {
                "operations": [{"op": "update", "collection": "c", "id": "i", "changes": {}}],
                "answer": "x",
            },
            "changes",
        ),
        (
            {"operations": [{"op": "delete", "collection": "", "id": "i"}], "answer": "x"},
            "collection",
        ),
        (
            {
                "operations": [{"op": "allocate", "counter": "t", "bind": "not a name"}],
                "answer": "x",
            },
            "bind",
        ),
        (
            {
                "operations": [
                    {"op": "allocate", "counter": "t", "bind": "n"},
                    {"op": "allocate", "counter": "u", "bind": "n"},
                ],
                "answer": "x",
            },
            "already bound",
        ),
        (
            {
                "operations": [
                    {"op": "delete", "collection": "c", "id": "T-{{n}}"},
                    {"op": "allocate", "counter": "t", "bind": "n"},
                ],
                "answer": "x",
            },
            "{{n}}",
        ),
        ({"operations": [], "answer": "T-{{missing}}"}, "{{missing}}"),
        ({"operations": [], "answer": "x", "gap": 3}, "gap"),
    ],
)
def test_every_malformed_plan_says_what_is_wrong_in_words_the_model_can_act_on(plan, message):
    errors = validate_plan(parsed(plan))
    assert errors and any(message in error for error in errors), errors


def test_a_plan_with_too_many_operations_is_refused():
    plan = {"operations": [{"op": "delete", "collection": "c", "id": f"i{n}"} for n in range(200)]}
    assert any("at most" in e for e in validate_plan(parsed({**plan, "answer": "x"})))


def test_asking_for_state_the_node_did_not_declare_is_a_plan_of_its_own():
    plan = parsed({"needs_state": "the ticket's history"})
    assert plan.needs_state == "the ticket's history" and validate_plan(plan) == []
    mixed = parsed(
        {"needs_state": "x", "operations": [{"op": "delete", "collection": "c", "id": "i"}]}
    )
    assert any("needs_state" in e for e in validate_plan(mixed))
    assert any("needs_state" in e for e in validate_plan(parsed({"needs_state": "  "})))


def test_bindings_fill_every_string_of_a_value_and_leave_the_rest_alone():
    filled = fill_bindings({"a": ["T-{{n}}", 5, None], "b": {"c": "{{ n }}"}}, {"n": 7})
    assert filled == {"a": ["T-7", 5, None], "b": {"c": "7"}}


def test_a_binding_nobody_made_is_an_error_not_a_blank():
    with pytest.raises(KeyError, match="missing"):
        fill_bindings("T-{{missing}}", {"n": 7})


def test_the_answer_is_printed_as_text_when_it_is_text_and_as_compact_json_otherwise():
    assert render_answer("hello\nworld") == "hello\nworld"
    assert render_answer({"ok": True, "n": 1}) == '{"ok":true,"n":1}'
    assert render_answer(None) == "null"
