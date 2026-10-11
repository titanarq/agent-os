"""The contract of the chat's new item kinds, request fields and keys (agent-os#179): shapes only."""

from __future__ import annotations

import json

import pytest
import yaml

from agent_os.lib import load_agents_config
from agent_os.product.interpreter.constants import InterpreterRefused
from agent_os.product.interpreter.items import parse_item
from agent_os.product.interpreter.request import parse_request
from agent_os.product.session_ingest.chat.reader import read_schema_2
from agent_os.product.session_ingest.session_file import SessionFileError
from tests.product.puntal.interpreter.interpreter_support import EXAMPLE_CONFIG, request_json

BASE = {"summary": "S", "from_messages": [0], "id": "item-1"}
VERDICT = {**BASE, "kind": "verdict", "verdict": "reject", "invocations": ["inv-9"], "note": "no"}
PUNTAL_CHANGE = {
    **BASE,
    "kind": "puntal_change",
    "node": "uc-a",
    "page": "/p",
    "invocations": ["i"],
}
ANSWER = {**BASE, "kind": "answer", "node": "uc-a", "question": "Cap?", "answer_text": "None"}
QUESTION = {"node": "uc-a", "question": "Cap?", "default_answer": "No cap."}


def parsed(raw):
    return parse_item(raw, where="items[0]", message_count=1, id_of_new=None)


@pytest.mark.parametrize("raw", [VERDICT, PUNTAL_CHANGE, ANSWER])
def test_the_new_kinds_round_trip_through_the_parser(raw):
    item, problems = parsed(raw)
    assert problems == []
    shown = item.as_json()
    assert {key: shown[key] for key in raw if key not in ("from_messages",)} == {
        key: value for key, value in raw.items() if key != "from_messages"
    }


def test_an_item_without_the_new_fields_prints_none_of_them():
    item, _ = parsed({**BASE, "kind": "change"})
    assert set(item.as_json()) == {
        "id",
        "kind",
        "summary",
        "node",
        "page",
        "from_messages",
        "withdrawn",
    }


@pytest.mark.parametrize(
    ("raw", "fragment"),
    [
        ({**VERDICT, "verdict": "maybe"}, "`verdict` must be one of"),
        ({**VERDICT, "invocations": ["a", "b"]}, "exactly one id"),
        ({**VERDICT, "invocations": []}, "exactly one id"),
        ({**ANSWER, "answer_text": None}, "needs `answer_text`"),
        ({**ANSWER, "question": ""}, "`question` must be text or null"),
        ({**BASE, "kind": "change", "invocations": "inv-1"}, "`invocations` must be a list"),
    ],
)
def test_a_malformed_new_item_is_refused_with_its_reason(raw, fragment):
    item, problems = parsed(raw)
    assert item is None and any(fragment in problem for problem in problems)


def read(*rows):
    document = {
        "id": "s",
        "opened_at": "2026-10-10T10:00:00Z",
        "status": "open",
        "cases": [],
        "comments": [{"role": "owner", "text": "hi"}],
        "questions": [],
        "items": list(rows),
    }
    return read_schema_2(document, "session.json").items


def test_the_session_reader_keeps_the_new_kinds_and_fields():
    verdict, change, answer = read(VERDICT, PUNTAL_CHANGE, ANSWER)
    assert (verdict.verdict, verdict.invocations, verdict.note) == ("reject", ("inv-9",), "no")
    assert change.kind == "puntal_change" and change.invocations == ("i",)
    assert (answer.question, answer.answer_text) == ("Cap?", "None")


def test_the_session_reader_refuses_an_unknown_verdict_and_bad_invocations():
    with pytest.raises(SessionFileError, match="item verdict 'maybe'"):
        read({**VERDICT, "verdict": "maybe"})
    with pytest.raises(SessionFileError, match="`invocations` is not a list"):
        read({**VERDICT, "invocations": [1]})


def request(**fields):
    return parse_request(request_json(**fields), tree_root=None)


def test_the_request_carries_invocations_and_the_open_question():
    entry = {
        "invocation_id": "inv-1",
        "action": "resend",
        "node": "uc-a",
        "page": "/p",
        "at": "t",
        "answer": "ok",
    }
    carried = request(invocations=[entry], pending_question=QUESTION)
    assert carried.invocations[0].invocation_id == "inv-1" and carried.invocations[0].answer == "ok"
    assert carried.pending_question.default_answer == "No cap." and carried.ask is None
    asking = json.loads(request_json(ask=QUESTION))
    del asking["message"]
    assert parse_request(json.dumps(asking), tree_root=None).ask.question == "Cap?"
    assert request().invocations == () and request().pending_question is None


@pytest.mark.parametrize(
    "fields",
    [
        {"invocations": "x"},
        {"invocations": [{"action": "a"}]},
        {
            "invocations": [
                {"invocation_id": "a", "action": "x"},
                {"invocation_id": "a", "action": "y"},
            ]
        },
        {"pending_question": {"node": "uc-a"}},
        {"ask": "why"},
        {"ask": QUESTION, "pending_question": QUESTION},
    ],
)
def test_a_malformed_request_field_is_refused(fields):
    with pytest.raises(InterpreterRefused):
        request(**fields)


def config_with(tmp_path, **sections):
    data = yaml.safe_load(EXAMPLE_CONFIG.read_text())
    for name, keys in sections.items():
        data[name] = {**data.get(name, {}), **keys}
    path = tmp_path / "agents.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return load_agents_config(path)


def test_the_two_new_keys_default_and_validate(tmp_path):
    config = config_with(tmp_path)
    assert config.interpreter.max_invocations == 5 and config.sessions.mechanism_repository == ""
    configured = config_with(
        tmp_path, interpreter={"max_invocations": 3}, sessions={"mechanism_repository": "o/n"}
    )
    assert configured.interpreter.max_invocations == 3
    assert configured.sessions.mechanism_repository == "o/n"
    for bad in (
        {"interpreter": {"max_invocations": 0}},
        {"sessions": {"mechanism_repository": "x"}},
    ):
        with pytest.raises((ValueError, SystemExit)):
            config_with(tmp_path, **bad)


def test_the_example_config_documents_both_keys():
    text = EXAMPLE_CONFIG.read_text()
    assert "max_invocations: 5" in text and 'mechanism_repository: ""' in text
