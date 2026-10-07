"""The reply grammar of a session, and its resolution against the frozen batch."""

from __future__ import annotations

import pytest

from agent_os.product.sessions.reply import parse_reply, resolve_reply

FROZEN = {
    "questions": [
        {"number": 1, "node": "fr-a", "question": "Sort order?", "default_answer": "newest first"},
        {"number": 2, "node": "fr-b", "question": "Share?", "default_answer": "author only"},
        {"number": 3, "node": "fr-c", "question": "Export?", "default_answer": "csv"},
    ],
    "digest": [{"number": 1, "judgment_id": "j-1", "node": "fr-a", "decision": "weekly"}],
}


def test_the_documented_example_parses_into_an_accepted_default_and_an_own_answer():
    reply = resolve_reply(["1: yes; 3: no, rather json lines"], FROZEN)
    assert [(a.number, a.answer, a.accepted_default) for a in reply.answers] == [
        (1, "newest first", True),
        (3, "json lines", False),
    ]


@pytest.mark.parametrize(
    "text",
    ["3: no, rather json", "3: no: json", "3: No - json", "3: no, instead json.", "3: json"],
)
def test_every_way_of_giving_an_own_answer_reads_the_same(text):
    assert parse_reply(text).answers[3].text == "json"


def test_a_bare_no_declines_the_default_without_an_answer_and_leaves_the_question_open():
    reply = resolve_reply(["2: no"], FROZEN)
    assert reply.answers == [] and reply.declined_numbers == [2]


def test_a_semicolon_inside_an_answer_stays_in_it_and_line_breaks_separate_items():
    reply = resolve_reply(["1: only; never shared\n2: yes"], FROZEN)
    assert reply.answers[0].answer == "only; never shared"
    assert reply.answers[1].accepted_default


def test_a_later_answer_to_the_same_number_wins_even_across_comments():
    reply = resolve_reply(["1: weekly", "chatting\n1: monthly"], FROZEN)
    assert [a.answer for a in reply.answers] == ["monthly"]


def test_an_unknown_number_is_reported_and_never_guessed():
    reply = resolve_reply(["9: yes; reclaim 7"], FROZEN)
    assert reply.answers == []
    assert reply.problems == [
        "there is no question 9 in this session",
        "there is no digest entry 7 in this session",
    ]


def test_a_reclaim_picks_the_digest_entry():
    reply = resolve_reply(["reclaim 1"], FROZEN)
    assert reply.reclaimed_digest_entries == [FROZEN["digest"][0]]


def test_text_that_is_not_an_item_is_ignored():
    assert parse_reply("thanks, will look at it").answers == {}
