"""An interpreted item's optional `status`: its contract (agent-os#169) and what `test-ingest` does
with it while `sessions.confirm_before_dispatch` is true (agent-os#171)."""

from __future__ import annotations

import json

import pytest
from sessions_support import (
    QUESTION,
    ChatTracker,
    chat_case,
    chat_comment,
    chat_document,
    chat_item,
    config_file,
    what_question,
    write_node,
)

from agent_os.product.interpreter.items import parse_item
from agent_os.product.session_ingest import cli as ingest_cli
from agent_os.product.session_ingest.chat.reader import read_schema_2
from agent_os.product.session_ingest.session_file import SessionFileError
from agent_os.product.sessions.cli import main

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


@pytest.fixture
def make_host(tmp_path, monkeypatch):
    def build(*, guard: bool):
        root = tmp_path / "product"
        write_node(root, "goal-a", "goal")
        write_node(
            root,
            "fr-a",
            "functional-requirement",
            parent="goal-a",
            experiments=[what_question(QUESTION, "No cap.")],
        )
        write_node(root, "uc-bad", "use-case", parent="fr-a", state="improvised")
        sessions = tmp_path / "sessions"
        sessions.mkdir()
        config = config_file(
            tmp_path,
            confirm_before_dispatch=guard,
            ticket_budget_class="mechanical-qwen",
            test_sessions_dir=str(sessions),
        )
        tracker = ChatTracker()
        monkeypatch.setattr(ingest_cli, "build_tracker", lambda: tracker)
        monkeypatch.setenv("WORKER_CACHE_DIR", str(tmp_path / "cache"))
        monkeypatch.setenv("AGENT_CACHE_DIR", str(tmp_path / "puntal"))
        monkeypatch.setenv("AGENT_OS_HOST_ROOT", str(tmp_path))
        return sessions, tracker, config

    return build


def write_session(sessions, items, comments=None, cases=None) -> None:
    comments = comments or [chat_comment("one"), chat_comment("two"), chat_comment("three")]
    document = chat_document(comments, cases or [], items=items)
    (sessions / "a.json").write_text(json.dumps(document), encoding="utf-8")


def three_changes() -> list[dict]:
    return [
        chat_item(1, "change", "Approved change", [0], status="approved", node="uc-bad"),
        chat_item(2, "change", "Proposed change", [1], status="proposed", node="uc-bad"),
        chat_item(3, "change", "Status-less change", [2]),
    ]


def ingest(config, *argv) -> int:
    return main(["test-ingest", *argv], config_path=config)


def test_guard_on_launches_only_the_approved_change_and_lists_the_rest(make_host, capsys):
    sessions, tracker, config = make_host(guard=True)
    write_session(sessions, three_changes())
    assert ingest(config, "--apply") == 0
    out = capsys.readouterr().out
    assert "proposed: item-2: Proposed change -- waiting for the owner's word in the chat" in out
    assert "proposed: item-3: Status-less change -- waiting" in out
    assert len(tracker.opened) == 1 and "item.item-1" in tracker.opened[0][1]
    (block,) = json.loads((sessions / "understood.json").read_text())["sessions"]
    assert [(p["id"], p["status"]) for p in block["proposals"]] == [
        ("item-2", "proposed"),
        ("item-3", "proposed"),
    ]
    assert set(block["proposals"][0]) == {
        "id",
        "status",
        "summary",
        "node",
        "page",
        "from_messages",
    }
    assert [c["issue"] for c in block["changes"]] == [101]


def test_guard_off_ignores_the_status(make_host, capsys):
    sessions, tracker, config = make_host(guard=False)
    write_session(sessions, three_changes())
    assert ingest(config, "--apply") == 0
    assert "waiting for the owner" not in capsys.readouterr().out
    assert len(tracker.opened) == 3
    (block,) = json.loads((sessions / "understood.json").read_text())["sessions"]
    assert block["proposals"] == [] and block["held"] == []


def test_guard_on_holds_the_raw_text_fallbacks_and_shows_them_in_understood(make_host, capsys):
    sessions, tracker, config = make_host(guard=True)
    comments = [chat_comment("no warning", state="needs_work", case="uc-bad")]
    write_session(sessions, [], comments, [chat_case("uc-bad", "needs_work")])
    assert ingest(config, "--apply") == 0
    out = capsys.readouterr().out
    assert "held: " in out and "-- no interpreter read it" in out
    assert tracker.opened == []
    (block,) = json.loads((sessions / "understood.json").read_text())["sessions"]
    assert [h["node"] for h in block["held"]] == ["uc-bad"] and block["changes"] == []


def test_dry_run_opens_nothing(make_host):
    sessions, tracker, config = make_host(guard=True)
    write_session(sessions, three_changes())
    assert ingest(config) == 0
    assert tracker.opened == [] and not (sessions / "understood.json").exists()
