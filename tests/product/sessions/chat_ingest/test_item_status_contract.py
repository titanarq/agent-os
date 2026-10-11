"""An interpreted item's optional `status`: its contract (agent-os#169) and what `test-ingest` does
with it while `sessions.confirm_before_dispatch` is true (agent-os#171)."""

from __future__ import annotations

import json
import pathlib

import pytest
from sessions_support import (
    QUESTION,
    SESSION,
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


INVOCATION = "inv-1"
VERSIONS = {"model": "m-1", "prompt": "p-1"}
SESSION_KEY = f"chat-verdict.{SESSION}.item-1"


def verdict_item(*, status: str, invocation: str = INVOCATION) -> list[dict]:
    return [
        chat_item(
            1,
            "verdict",
            "The answer was wrong",
            [0],
            status=status,
            verdict="reject",
            note="It ignores the red one",
            invocations=[invocation],
        )
    ]


def write_telemetry(sessions) -> pathlib.Path:
    row = {"invocation_id": INVOCATION, "action": "resend", "node": "uc-bad", "versions": VERSIONS}
    puntal = sessions.parent / "puntal"
    puntal.mkdir(exist_ok=True)
    (puntal / "telemetry.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    return puntal / "feedback.jsonl"


def feedback_rows(feedback_file) -> list[dict]:
    if not feedback_file.exists():
        return []
    return [json.loads(line) for line in feedback_file.read_text().splitlines()]


def test_an_approved_verdict_is_recorded_once_against_its_invocation(make_host, capsys):
    sessions, _, config = make_host(guard=True)
    feedback_file = write_telemetry(sessions)
    write_session(sessions, verdict_item(status="approved"))
    assert ingest(config, "--apply") == 0
    assert "verdict: reject on invocation inv-1" in capsys.readouterr().out
    (row,) = feedback_rows(feedback_file)
    assert (row["verdict"], row["note"], row["action"], row["node"], row["versions"]) == (
        "reject",
        "It ignores the red one",
        "resend",
        "uc-bad",
        VERSIONS,
    )
    assert row["key"] == SESSION_KEY
    assert ingest(config, "--apply", "--session", SESSION) == 0
    assert "(already recorded)" in capsys.readouterr().out
    assert len(feedback_rows(feedback_file)) == 1


def test_a_proposed_verdict_waits_and_is_listed_for_the_owner(make_host, capsys):
    sessions, _, config = make_host(guard=True)
    feedback_file = write_telemetry(sessions)
    write_session(sessions, verdict_item(status="proposed"))
    assert ingest(config, "--apply") == 0
    assert "proposed: item-1" in capsys.readouterr().out
    assert feedback_rows(feedback_file) == []
    (block,) = json.loads((sessions / "understood.json").read_text())["sessions"]
    assert [p["id"] for p in block["proposals"]] == ["item-1"]


def test_a_verdict_on_an_unknown_invocation_is_a_problem_and_writes_nothing(make_host, capsys):
    sessions, _, config = make_host(guard=True)
    feedback_file = write_telemetry(sessions)
    write_session(sessions, verdict_item(status="approved", invocation="inv-9"))
    assert ingest(config, "--apply") == 1
    assert "item-1: no invocation 'inv-9'" in capsys.readouterr().err
    assert feedback_rows(feedback_file) == []


def test_the_summary_counts_a_chat_verdict_once_in_its_own_session(make_host, capsys):
    sessions, _, config = make_host(guard=True)
    feedback_file = write_telemetry(sessions)
    write_session(sessions, verdict_item(status="approved"))
    ingest(config, "--apply")
    capsys.readouterr()
    with feedback_file.open("a") as handle:
        handle.write(json.dumps(feedback_rows(feedback_file)[0]) + "\n")
    ingest(config, "--session", SESSION)
    assert "resend on uc-bad: accepted 0, rejected 1 (It ignores the red one), retried 0" in (
        capsys.readouterr().out
    )
