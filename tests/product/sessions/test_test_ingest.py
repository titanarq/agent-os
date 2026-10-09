"""`agent-os-sessions test-ingest`: closed sessions into the tree and the backlog, no network."""

from __future__ import annotations

import json

import pytest
import yaml
from conftest import EXAMPLE_CONFIG

from agent_os.product.session_ingest import cli as ingest_cli
from agent_os.product.session_ingest.rework_ticket import rework_key
from agent_os.product.sessions.cli import main
from agent_os.product.tree.loader import load_tree

QUESTION = "How many ads may an account keep open?"
CLOSED_AT = "2026-10-09T17:30:00+02:00"


class FakeTracker:
    def __init__(self) -> None:
        self.opened: list[tuple[str, str, list[str]]] = []
        self.known: dict[tuple[str, str], int] = {}

    def find(self, session_id: str, node_id: str) -> int | None:
        return self.known.get((session_id, node_id))

    def open(self, title: str, body: str, labels: list[str]) -> int:
        self.opened.append((title, body, labels))
        return 100 + len(self.opened)


def write_node(root, node_id: str, node_type: str, **fields) -> None:
    frontmatter = {"id": node_id, "type": node_type, "title": f"T {node_id}", "sources": ["brief"]}
    frontmatter.update(
        {"verification": [{"judge": "holds"}]} if node_type == "goal" else {"mechanism": "pending"}
    )
    frontmatter.update(fields)
    text = yaml.safe_dump(frontmatter, sort_keys=False)
    (root / f"{node_id}.md").write_text(f"---\n{text}---\nDescription.\n", encoding="utf-8")


def session_document(session_id="ts-20261009-172808-b2cf80", status="closed", **fields) -> dict:
    return {
        "id": session_id,
        "branch": "fr-a",
        "status": status,
        "opened_at": "2026-10-09T17:00:00+02:00",
        "closed_at": CLOSED_AT if status == "closed" else None,
        "cases": [
            {"node": "uc-ok", "title": "ok", "verdict": "accept", "note": ""},
            {
                "node": "uc-bad",
                "title": "bad",
                "verdict": "reject",
                "note": "no warning\n## Not a heading",
            },
            {"node": "uc-skip", "title": "skip", "verdict": "not_tried", "note": ""},
        ],
        "questions": [
            {
                "node": "fr-a",
                "question": QUESTION,
                "default_answer": "No cap.",
                "date": "2026-10-01",
                "answer": "At most 5.",
            },
            {
                "node": "fr-a",
                "question": "Other?",
                "default_answer": "Yes.",
                "date": "2026-10-01",
                "answer": None,
            },
        ],
        **fields,
    }


@pytest.fixture
def host(tmp_path, monkeypatch):
    root = tmp_path / "product"
    root.mkdir()
    write_node(root, "goal-a", "goal")
    questions = [
        {
            "kind": "question",
            "question": q,
            "outcome": "open",
            "date": "2026-10-01",
            "scope": "what",
            "default_answer": d,
        }
        for q, d in ((QUESTION, "No cap."), ("Other?", "Yes."))
    ]
    write_node(root, "fr-a", "functional-requirement", parent="goal-a", experiments=questions)
    for node_id in ("uc-ok", "uc-bad", "uc-skip"):
        write_node(root, node_id, "use-case", parent="fr-a", state="improvised")
    data = yaml.safe_load(EXAMPLE_CONFIG.read_text())
    data["tree"] = {
        "root": "product",
        "ticket_budget_class": "mechanical-qwen",
        "test_sessions_dir": str(tmp_path / "sessions"),
    }
    (tmp_path / "sessions").mkdir()
    (tmp_path / "agents.yaml").write_text(yaml.safe_dump(data, sort_keys=False))
    tracker = FakeTracker()
    monkeypatch.setattr(ingest_cli, "build_tracker", lambda: tracker)
    monkeypatch.setenv("WORKER_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("AGENT_CACHE_DIR", str(tmp_path / "puntal"))
    monkeypatch.setenv("AGENT_OS_HOST_ROOT", str(tmp_path))
    (tmp_path / "sessions" / "a.json").write_text(json.dumps(session_document()))
    return tmp_path, tracker


def ingest(tmp_path, *argv) -> int:
    return main(["test-ingest", *argv], config_path=tmp_path / "agents.yaml")


def test_the_default_run_prints_the_plan_and_writes_nothing(host, capsys):
    tmp_path, tracker = host
    assert ingest(tmp_path) == 0
    out = capsys.readouterr().out
    assert f"write answer: fr-a: {QUESTION} -> At most 5." in out
    assert "unanswered: fr-a: Other? -- nothing written, the default stands" in out
    assert "accepted: uc-ok" in out and "rejected: uc-bad" in out and "not tried: uc-skip" in out
    assert "dry run" in out
    assert tracker.opened == [] and not (tmp_path / "cache").exists()
    assert load_tree(tmp_path / "product").nodes["fr-a"].experiments[0].outcome == "open"


def test_apply_writes_answers_and_acceptances_and_opens_one_rework_issue(host):
    tmp_path, tracker = host
    assert ingest(tmp_path, "--apply") == 0
    tree = load_tree(tmp_path / "product")
    first, second = tree.nodes["fr-a"].experiments
    assert (first.outcome, first.finding) == ("answered", "At most 5.")
    assert second.outcome == "open"
    accepted = tree.nodes["uc-ok"].acceptances
    assert [(a.session, str(a.date)) for a in accepted] == [
        ("ts-20261009-172808-b2cf80", "2026-10-09")
    ]
    assert tree.nodes["uc-bad"].acceptances == [] and tree.nodes["uc-skip"].acceptances == []
    ((title, body, labels),) = tracker.opened
    assert "uc-bad" in title and "<!-- node: uc-bad -->" in body
    assert f"<!-- key: {rework_key('ts-20261009-172808-b2cf80', 'uc-bad')} -->" in body
    assert "> ## Not a heading" in body and "type:bug" in labels
    assert not tree.defects


def test_a_second_run_finds_nothing_to_ingest(host, capsys):
    tmp_path, tracker = host
    ingest(tmp_path, "--apply")
    capsys.readouterr()
    assert ingest(tmp_path, "--apply") == 0
    assert "no closed test session is waiting" in capsys.readouterr().out
    assert len(tracker.opened) == 1


def test_forcing_a_session_again_repeats_no_effect(host, capsys):
    tmp_path, tracker = host
    ingest(tmp_path, "--apply")
    tracker.known[("ts-20261009-172808-b2cf80", "uc-bad")] = 101
    capsys.readouterr()
    assert ingest(tmp_path, "--apply", "--session", "ts-20261009-172808-b2cf80") == 0
    out = capsys.readouterr().out
    assert "already opened as #101" in out and "(already done)" in out
    assert len(tracker.opened) == 1
    assert len(load_tree(tmp_path / "product").nodes["uc-ok"].acceptances) == 1


def test_an_open_session_is_ignored(host, capsys):
    tmp_path, tracker = host
    (tmp_path / "sessions" / "a.json").write_text(json.dumps(session_document(status="open")))
    assert ingest(tmp_path, "--apply") == 0
    assert "no closed test session is waiting" in capsys.readouterr().out and tracker.opened == []


def test_a_node_the_tree_lacks_is_a_problem_and_the_session_stays_pending(host, capsys):
    tmp_path, _ = host
    document = session_document()
    document["cases"][0]["node"] = "uc-gone"
    (tmp_path / "sessions" / "a.json").write_text(json.dumps(document))
    assert ingest(tmp_path, "--apply") == 1
    assert "uc-gone: no such node" in capsys.readouterr().err
    assert ingest(tmp_path) == 1


def test_a_missing_sessions_directory_is_refused_by_the_key_that_names_it(host, capsys):
    tmp_path, _ = host
    assert ingest(tmp_path, "--sessions-dir", str(tmp_path / "nowhere")) == 1
    assert "tree.test_sessions_dir" in capsys.readouterr().err


def test_a_session_file_that_breaks_the_contract_is_named_and_the_rest_goes_on(host, capsys):
    tmp_path, _ = host
    (tmp_path / "sessions" / "b.json").write_text(json.dumps({"id": "x", "status": "closed"}))
    assert ingest(tmp_path) == 1
    captured = capsys.readouterr()
    assert "b.json" in captured.err and "write answer" in captured.out


def test_the_verdicts_of_the_session_window_are_summarised(host, capsys):
    tmp_path, _ = host
    lines = [
        {
            "recorded_at": "2026-10-09T15:10:00.000+00:00",
            "verdict": "accept",
            "action": "create-ad",
            "node": "uc-ok",
        },
        {
            "recorded_at": "2026-10-09T15:11:00.000+00:00",
            "verdict": "reject",
            "note": "wrong tone",
            "action": "create-ad",
            "node": "uc-ok",
        },
        {
            "recorded_at": "2026-10-09T15:12:00.000+00:00",
            "verdict": "retry",
            "action": "create-ad",
            "node": "uc-ok",
        },
        {
            "recorded_at": "2026-10-08T10:00:00.000+00:00",
            "verdict": "accept",
            "action": "create-ad",
            "node": "uc-ok",
        },
    ]
    (tmp_path / "puntal").mkdir()
    (tmp_path / "puntal" / "feedback.jsonl").write_text(
        "\n".join(json.dumps(line) for line in lines)
    )
    ingest(tmp_path)
    assert (
        "create-ad on uc-ok: accepted 1, rejected 1 (wrong tone), retried 1"
        in capsys.readouterr().out
    )
