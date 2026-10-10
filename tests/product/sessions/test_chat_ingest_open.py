"""`agent-os-sessions test-ingest` on a chat session still open (schema 2): the app has no button that
closes it, so the session is read as the owner goes on, again on every run, and nothing is repeated."""

from __future__ import annotations

import datetime
import json

import pytest
from sessions_support import (
    SESSION,
    build_chat_host,
    chat_document,
    ingest,
    write_session,
)
from sessions_support import (
    chat_case as case,
)
from sessions_support import (
    chat_comment as comment,
)
from sessions_support import (
    chat_item as item,
)

from agent_os.product.session_ingest.registry import ingested_session_ids
from agent_os.product.tree.loader import load_tree

EARLIER_SESSION = "ts-20261009-090000-aaa111"


@pytest.fixture
def host(tmp_path, monkeypatch):
    return build_chat_host(tmp_path, monkeypatch)


def open_document(comments, cases, **fields) -> dict:
    return chat_document(comments, cases, status="open", closed_at=None, **fields)


def understood(host) -> dict:
    return json.loads((host[3] / "understood.json").read_text())


def test_an_open_session_launches_what_the_interpreter_understood_and_is_read_again_next_run(
    host, capsys
):
    comments = [comment("Show the red warning", case="uc-bad"), comment("Ten ads per account")]
    items = [
        item(1, "change", "Show the red warning", [0], node="uc-bad"),
        item(2, "decision", "Cap the ads at ten", [1]),
    ]
    write_session(host, open_document(comments, [case("uc-bad", "needs_work")], items=items))
    assert ingest(host, "--apply") == 0
    assert "(chat, open since 2026-10-10)" in capsys.readouterr().out
    ((_, body, _),) = host[1].opened
    assert f"<!-- key: test-change.{SESSION}.item.item-1 -->" in body
    (block,) = understood(host)["sessions"]
    assert (block["status"], block["closed_at"]) == ("open", None)
    assert block["opened_at"] == "2026-10-10T10:00:00+02:00"
    assert [d["id"] for d in block["decisions"]] == ["item-2"] and block["changes"][0][
        "issue"
    ] == 101
    assert ingested_session_ids(host[0] / "cache") == set()
    assert tree_answer(host) == "At most 5."

    assert ingest(host, "--apply") == 0
    out = capsys.readouterr().out
    assert "already opened as #101" in out and "wrote" not in out
    assert len(host[1].opened) == 1 and understood(host)["sessions"] == [block]


def tree_answer(host) -> str:
    return load_tree(host[0] / "product").nodes["fr-a"].experiments[0].finding


def test_an_item_that_arrives_later_is_launched_once_and_its_raw_text_never_is(host, capsys):
    comments = [comment("There is no warning", state="needs_work", case="uc-bad")]
    cases = [case("uc-bad", "needs_work")]
    write_session(host, open_document(comments, cases))
    assert ingest(host, "--apply") == 0
    out = capsys.readouterr().out
    assert "waiting: Rework `uc-bad`" in out and "the session is open" in out
    assert host[1].opened == [] and not (host[3] / "understood.json").exists()

    comments.append(comment("Which warning?", role="agent", case="uc-bad"))
    items = [item(1, "change", "Show a warning", [0], node="uc-bad")]
    write_session(host, open_document(comments, cases, items=items))
    assert ingest(host, "--apply") == 0
    assert "waiting" not in capsys.readouterr().out and len(host[1].opened) == 1

    write_session(host, chat_document(comments, cases, items=items))
    assert ingest(host, "--apply") == 0
    assert len(host[1].opened) == 1
    assert ingested_session_ids(host[0] / "cache") == {SESSION}


def test_when_the_session_closes_what_no_item_covered_is_launched_by_the_state_of_its_case(host):
    comments = [
        comment("There is no warning", state="needs_work", case="uc-bad"),
        comment("Prices need the euro sign"),
    ]
    cases = [case("uc-bad", "needs_work")]
    write_session(host, open_document(comments, cases))
    assert ingest(host, "--apply") == 0 and host[1].opened == []
    write_session(host, chat_document(comments, cases))
    assert ingest(host, "--apply") == 0
    assert f"<!-- key: test-rework.{SESSION}.uc-bad -->" in host[1].opened[0][1]
    assert len(host[1].opened) == 2
    assert [c["origin"] for c in understood(host)["sessions"][0]["changes"]] == [
        "rework",
        "general",
    ]


def test_a_perfect_in_an_open_session_is_accepted_at_once_on_the_day_it_opened(host):
    comments = [comment("great", state="perfect", case="uc-ok")]
    write_session(host, open_document(comments, [case("uc-ok", "perfect")]))
    assert ingest(host, "--apply") == 0
    (acceptance,) = load_tree(host[0] / "product").nodes["uc-ok"].acceptances
    assert (acceptance.session, acceptance.date) == (SESSION, datetime.date(2026, 10, 10))
    assert ingest(host, "--apply") == 0
    assert len(load_tree(host[0] / "product").nodes["uc-ok"].acceptances) == 1


def test_an_item_withdrawn_after_it_was_launched_warns_with_its_issue_and_launches_nothing(
    host, capsys
):
    comments = [comment("Redo the footer", case="uc-bad")]
    cases = [case("uc-bad", "needs_work")]
    items = [item(1, "change", "Redo the footer", [0], node="uc-bad")]
    write_session(host, open_document(comments, cases, items=items))
    assert ingest(host, "--apply") == 0 and len(host[1].opened) == 1
    capsys.readouterr()
    write_session(host, open_document(comments, cases, items=[{**items[0], "withdrawn": True}]))
    assert ingest(host, "--apply") == 0
    out = capsys.readouterr().out
    assert "withdrawn: item-1" in out and "already launched as #101" in out
    assert len(host[1].opened) == 1


def test_the_thread_of_a_case_crosses_sessions_and_each_message_is_a_session_and_a_position(host):
    first = chat_document(
        [comment("Show a warning", case="uc-bad")],
        [case("uc-bad", "needs_work")],
        session_id=EARLIER_SESSION,
        items=[item(1, "change", "Show a warning", [0], node="uc-bad")],
    )
    second = open_document(
        [comment("Make the warning red", case="uc-bad")],
        [case("uc-bad", "needs_work")],
        items=[item(1, "change", "Make the warning red", [0], node="uc-bad")],
    )
    first["closed_at"] = "2026-10-09T09:20:00+02:00"
    first["opened_at"] = "2026-10-09T09:00:00+02:00"
    write_session(host, second, "b.json")
    write_session(host, first, "a.json")
    assert ingest(host, "--apply") == 0
    keys = [body.split("<!-- key: ")[1].split(" -->")[0] for _, body, _ in host[1].opened]
    assert keys == [
        f"test-change.{EARLIER_SESSION}.item.item-1",
        f"test-change.{SESSION}.item.item-1",
    ]
    assert "Make the warning red" not in host[1].opened[0][1]
    assert [block["session"] for block in understood(host)["sessions"]] == [
        EARLIER_SESSION,
        SESSION,
    ]
    assert understood(host)["sessions"][0]["status"] == "closed"
    assert ingested_session_ids(host[0] / "cache") == {EARLIER_SESSION}
    assert tree_answer(host) == "At most 5."


def test_an_open_session_of_another_schema_is_still_nobodys_to_read(host, capsys):
    write_session(host, open_document([], [], schema=1) | {"schema": 1})
    write_session(host, open_document([], [], schema=3) | {"schema": 3}, "b.json")
    assert ingest(host, "--apply") == 0
    assert "no test session is waiting" in capsys.readouterr().out
