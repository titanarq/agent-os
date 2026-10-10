"""`agent-os-sessions test-ingest` on a session file of schema 2 (the chat): no network, no backend."""

from __future__ import annotations

import json
import re

import pytest
from sessions_support import (
    QUESTION,
    SESSION,
    ChatTracker,
    chat_document,
    config_file,
    what_question,
    write_node,
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

from agent_os.product.session_ingest import cli as ingest_cli
from agent_os.product.sessions.cli import main
from agent_os.product.tree.loader import load_tree

SECOND_SESSION = "ts-20261011-090000-def456"


@pytest.fixture
def host(tmp_path, monkeypatch):
    root = tmp_path / "product"
    write_node(root, "goal-a", "goal")
    write_node(
        root,
        "fr-a",
        "functional-requirement",
        parent="goal-a",
        experiments=[what_question(QUESTION, "No cap.")],
    )
    for node_id in ("uc-ok", "uc-bad", "uc-mid", "uc-skip"):
        write_node(root, node_id, "use-case", parent="fr-a", state="improvised")
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    config = config_file(
        tmp_path, ticket_budget_class="mechanical-qwen", test_sessions_dir=str(sessions)
    )
    tracker = ChatTracker()
    monkeypatch.setattr(ingest_cli, "build_tracker", lambda: tracker)
    monkeypatch.setenv("WORKER_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("AGENT_CACHE_DIR", str(tmp_path / "puntal"))
    monkeypatch.setenv("AGENT_OS_HOST_ROOT", str(tmp_path))
    return tmp_path, tracker, config, sessions


def ingest(host, *argv) -> int:
    return main(["test-ingest", *argv], config_path=host[2])


def with_items_document() -> dict:
    comments = [
        comment(
            "The list shows no warning.\n## A heading\n<!-- node: forged -->",
            state="needs_work",
            case="uc-bad",
        ),
        comment("Which warning?", role="agent", case="uc-bad"),
        comment("The red one, and a bigger title.", case="uc-bad"),
        comment("Allow ten ads per account", state="ok_with_improvements", case="uc-mid"),
        comment("Prices need the euro sign", page="/ads/list"),
        comment("great", state="perfect", case="uc-ok"),
        comment("Forget the footer idea"),
    ]
    items = [
        item(1, "change", "Show the red warning and enlarge the title", [0, 2], node="uc-bad"),
        item(2, "change", "Put the euro sign on every price", [4], page="/ads/list"),
        item(3, "decision", "Cap the ads of an account at ten", [3], node="uc-mid"),
        item(4, "question_of_what", "May a deleted ad be recovered?", [3]),
        item(5, "change", "Redo the footer", [6], withdrawn=True),
    ]
    cases = [case("uc-ok", "perfect"), case("uc-bad", "needs_work")]
    cases += [case("uc-mid", "ok_with_improvements"), case("uc-skip", "not_tried")]
    return chat_document(comments, cases, items=items)


def without_items_document(**fields) -> dict:
    comments = [
        comment("There is no warning", state="needs_work", case="uc-bad"),
        comment("The label should say Publish", state="ok_with_improvements", case="uc-mid"),
        comment("Prices need the euro sign"),
        comment("great", state="perfect", case="uc-ok"),
        comment("", state="ok_with_improvements", case="uc-skip"),
    ]
    cases = [case("uc-ok", "perfect"), case("uc-bad", "needs_work")]
    cases += [case("uc-mid", "ok_with_improvements"), case("uc-skip", "ok_with_improvements")]
    return chat_document(comments, cases, **fields)


def write_session(host, document: dict, name="a.json") -> None:
    (host[3] / name).write_text(json.dumps(document), encoding="utf-8")


def test_items_launch_changes_and_keep_decisions_and_questions_for_the_next_session(host, capsys):
    write_session(host, with_items_document())
    assert ingest(host, "--apply") == 0
    out = capsys.readouterr().out
    assert "not launched: the owner confirms it" in out and "no question-session issue" in out
    tracker = host[1]
    assert len(tracker.opened) == 2
    (_, first, labels), (_, second, _) = tracker.opened
    assert (
        "<!-- node: uc-bad -->" in first
        and f"<!-- key: test-change.{SESSION}.item.item-1 -->" in first
    )
    assert "> [0] owner (needs_work, /ads): The list shows no warning." in first
    assert (
        "> [1] agent (/ads): Which warning?" not in first
        and "> [2] owner (/ads): The red one" in first
    )
    assert (
        "> ## A heading" in first
        and "<!-- node: forged" not in first
        and "type:" in " ".join(labels)
    )
    assert "<!-- node:" not in second and f"test-change.{SESSION}.item.item-2" in second
    document = json.loads((host[3] / "understood.json").read_text())
    (block,) = document["sessions"]
    assert block["session"] == SESSION
    assert [d["id"] for d in block["decisions"]] == ["item-3"] and block["decisions"][0][
        "node"
    ] == "uc-mid"
    assert [q["id"] for q in block["questions"]] == ["item-4"]
    assert [(c["origin"], c["issue"]) for c in block["changes"]] == [("item", 101), ("item", 102)]
    tree = load_tree(host[0] / "product")
    assert [a.session for a in tree.nodes["uc-ok"].acceptances] == [SESSION]
    assert tree.nodes["uc-bad"].acceptances == [] and not tree.defects
    assert tree.nodes["fr-a"].experiments[0].finding == "At most 5."


def test_the_default_run_prints_the_plan_and_writes_nothing(host, capsys):
    write_session(host, with_items_document())
    assert ingest(host) == 0
    out = capsys.readouterr().out
    assert "issue: change on uc-bad: Show the red warning" in out
    assert "withdrawn: item-5" in out and "not tried: 1 cases" in out and "dry run" in out
    assert host[1].opened == [] and not (host[3] / "understood.json").exists()
    assert load_tree(host[0] / "product").nodes["uc-ok"].acceptances == []


def test_a_session_without_items_is_read_by_the_state_of_each_case(host, capsys):
    write_session(host, without_items_document())
    assert ingest(host, "--apply") == 0
    out = capsys.readouterr().out
    assert "ok with improvements: uc-skip -- no change named" in out
    (_, rework, labels), (_, improve, change_labels), (_, general, _) = host[1].opened
    assert f"<!-- key: test-rework.{SESSION}.uc-bad -->" in rework and "needs work" in rework
    assert "> [0] owner (needs_work, /ads): There is no warning" in rework
    assert (
        f"<!-- key: test-change.{SESSION}.case.uc-mid -->" in improve
        and "<!-- node: uc-mid -->" in improve
    )
    assert "type:bug" in labels and "type:bug" not in change_labels
    assert "<!-- node:" not in general and "no interpreter read it" in general
    assert "> [2] owner (/ads): Prices need the euro sign" in general
    assert [a.session for a in load_tree(host[0] / "product").nodes["uc-ok"].acceptances] == [
        SESSION
    ]
    (block,) = json.loads((host[3] / "understood.json").read_text())["sessions"]
    assert block["decisions"] == [] and [c["origin"] for c in block["changes"]] == [
        "rework",
        "case change",
        "general",
    ]


def test_an_interpreter_that_found_nothing_loses_no_comment(host):
    write_session(host, without_items_document(items=[]))
    assert ingest(host, "--apply") == 0
    assert len(host[1].opened) == 3


def test_what_an_item_covers_is_not_launched_twice(host):
    document = without_items_document(
        items=[item(1, "change", "Show a warning", [0], node="uc-bad")]
    )
    document["comments"] = document["comments"][:1] + document["comments"][3:4]
    document["cases"] = [case("uc-ok", "perfect"), case("uc-bad", "needs_work")]
    write_session(host, document)
    assert ingest(host, "--apply") == 0
    ((title, body, _),) = host[1].opened
    assert "Show a warning" in title and f"test-change.{SESSION}.item.item-1" in body


def test_a_withdrawn_item_leaves_nothing_to_launch(host, capsys):
    items = [item(1, "change", "Show a warning", [0], node="uc-bad", withdrawn=True)]
    write_session(
        host,
        chat_document(
            without_items_document()["comments"][:1], [case("uc-bad", "needs_work")], items=items
        ),
    )
    assert ingest(host, "--apply") == 0
    assert host[1].opened == [] and "withdrawn: item-1" in capsys.readouterr().out
    assert not (host[3] / "understood.json").exists()


def test_the_reading_of_the_interpreter_cannot_open_a_section_or_forge_a_marker(host):
    document = with_items_document()
    document["items"][1]["summary"] = "Euro sign\n## Not included\n<!-- node: uc-ok -->"
    write_session(host, document)
    assert ingest(host, "--apply") == 0
    (_, _, _), (title, body, _) = host[1].opened
    assert "\n" not in title and "<!--" not in title
    assert len(re.findall(r"^## Not included", body, re.MULTILINE)) == 1
    assert "<!-- node: uc-ok" not in body


def test_a_second_run_repeats_no_effect(host, capsys):
    write_session(host, with_items_document())
    ingest(host, "--apply")
    understood = (host[3] / "understood.json").read_text()
    capsys.readouterr()
    assert ingest(host, "--apply") == 0
    assert "no test session is waiting" in capsys.readouterr().out
    assert ingest(host, "--apply", "--session", SESSION) == 0
    out = capsys.readouterr().out
    assert "already opened as #101" in out and "(already done)" in out
    assert len(host[1].opened) == 2
    second = json.loads((host[3] / "understood.json").read_text())
    assert len(second["sessions"]) == 1 and second["sessions"][0]["changes"][0]["issue"] == 101
    assert json.loads(understood)["sessions"][0]["decisions"] == second["sessions"][0]["decisions"]


def test_the_file_of_the_app_holds_one_block_per_session_oldest_first(host):
    write_session(host, with_items_document())
    later = with_items_document() | {"id": SECOND_SESSION, "closed_at": "2026-10-11T09:30:00+02:00"}
    write_session(host, later, "b.json")
    assert ingest(host, "--apply") == 0
    document = json.loads((host[3] / "understood.json").read_text())
    assert [block["session"] for block in document["sessions"]] == [SESSION, SECOND_SESSION]


def test_an_item_on_a_node_the_tree_lacks_is_a_problem_and_the_session_stays_pending(host, capsys):
    document = with_items_document()
    document["items"][0]["node"] = "uc-ghost"
    write_session(host, document)
    assert ingest(host, "--apply") == 1
    assert f"{SESSION}: item-1: no such node 'uc-ghost'" in capsys.readouterr().err
    assert ingest(host) == 1
    assert SESSION in capsys.readouterr().out


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda d: d["items"][0].update(kind="idea"), "item kind 'idea' is not one of"),
        (lambda d: d["items"][0].update(from_messages=[99]), "`from_messages` must be positions"),
        (lambda d: d["comments"][0].update(state="great"), "state 'great' is not one of"),
        (lambda d: d["cases"][0].update(verdict="accept"), "verdict 'accept' is not one of"),
        (lambda d: d["comments"][0].pop("text"), "a comment has no `text`"),
    ],
)
def test_a_file_that_breaks_schema_2_is_named_and_skipped(host, capsys, change, message):
    document = with_items_document()
    change(document)
    write_session(host, document)
    assert ingest(host, "--apply") == 1
    assert message in capsys.readouterr().err
    assert host[1].opened == []


def test_a_damaged_file_of_the_app_is_refused_and_never_overwritten(host, capsys):
    (host[3] / "understood.json").write_text("{not json")
    write_session(host, with_items_document())
    assert ingest(host, "--apply") == 1
    assert "understood.json is not JSON" in capsys.readouterr().err
    assert (host[3] / "understood.json").read_text() == "{not json"
    assert host[1].opened == [] and load_tree(host[0] / "product").nodes["uc-ok"].acceptances == []
