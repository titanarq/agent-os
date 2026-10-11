"""An interpreted item's optional `status`, on the interpreter's side and the ingestion's (agent-os#169)."""

from __future__ import annotations

import pytest
from sessions_support import chat_comment, chat_document, chat_item

from agent_os.product.interpreter.items import parse_item
from agent_os.product.session_ingest.chat.reader import read_schema_2
from agent_os.product.session_ingest.session_file import SessionFileError

RAW = {"kind": "change", "summary": "Label it", "from_messages": [0], "id": "item-1"}


def parsed(**fields):
    return parse_item({**RAW, **fields}, where="items[0]", message_count=1, id_of_new=None)


def read_items(*items):
    document = chat_document([chat_comment("hi")], [], items=list(items))
    return read_schema_2(document, "session.json").items


@pytest.mark.parametrize("status", ["proposed", "approved"])
def test_an_interpreter_item_round_trips_its_status(status):
    item, problems = parsed(status=status)
    assert problems == [] and item.status == status
    assert item.as_json()["status"] == status


def test_an_interpreter_item_without_status_stays_without_it():
    item, _ = parsed()
    assert item.status is None and "status" not in item.as_json()


def test_the_interpreter_refuses_an_unknown_status():
    item, problems = parsed(status="done")
    assert item is None and "`status` must be one of" in problems[0]


def test_the_session_reader_keeps_the_status_and_its_absence():
    with_status, without = read_items(
        chat_item(1, "change", "A", [0], status="approved"), chat_item(2, "change", "B", [0])
    )
    assert with_status.status == "approved" and without.status is None


def test_the_session_reader_refuses_an_unknown_status_naming_the_file():
    with pytest.raises(SessionFileError, match=r"session\.json.*status 'done'"):
        read_items(chat_item(1, "change", "A", [0], status="done"))
