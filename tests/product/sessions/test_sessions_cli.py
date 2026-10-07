"""`agent-os-sessions` end to end against a fake `gh`: no network, no backend."""

from __future__ import annotations

import json

import pytest
from sessions_support import OWNER_LOGIN, FakeGh, config_file, what_question, write_node

from agent_os import issues
from agent_os.product.sessions import judgments, session_log
from agent_os.product.sessions.batch import build_batch
from agent_os.product.sessions.cli import main
from agent_os.product.sessions.render import render_session_body
from agent_os.product.tree.loader import load_tree

QUESTION = "Sort order of notes?"


@pytest.fixture
def gh(tmp_path, monkeypatch):
    monkeypatch.setattr(issues.time, "sleep", lambda _seconds: None)
    return FakeGh(tmp_path, monkeypatch)


@pytest.fixture
def tree_root(tmp_path):
    root = tmp_path / "product"
    write_node(root, "goal-a", "goal")
    write_node(
        root,
        "fr-a",
        "functional-requirement",
        parent="goal-a",
        experiments=[what_question(QUESTION, "newest first")],
    )
    return root


def run(tmp_path, *argv, **tree_keys):
    return main([str(part) for part in argv], config_path=config_file(tmp_path, **tree_keys))


def cache(tmp_path):
    return tmp_path / "cache"


def test_open_creates_one_blocked_on_human_issue_and_logs_the_session(
    tmp_path, tree_root, gh, capsys
):
    gh.set_route("widgets/issues -X POST", {"number": 42})
    judgments.record_judgment(
        cache(tmp_path),
        role="refiner",
        kind="soft",
        node="fr-a",
        decision="Weekly view.",
        scope="how",
        versions={},
    )
    assert run(tmp_path, "open", "--root", tree_root) == 0
    assert "opened session issue #42: 1 question(s)" in capsys.readouterr().out
    creation = [call for call in gh.calls() if "POST" in call]
    assert len(creation) == 1
    assert "labels[]=status:blocked-on-human" in creation[0]
    body = next(arg for arg in creation[0] if arg.startswith("body="))
    assert QUESTION in body and "Weekly view." in body
    assert session_log.last_session_opened_at(cache(tmp_path)) is not None


def test_the_next_digest_holds_only_what_came_after_the_last_session(tmp_path, tree_root, gh):
    gh.set_route("widgets/issues -X POST", {"number": 42})
    judgments.record_judgment(
        cache(tmp_path), role="r", kind="k", node=None, decision="Old.", scope="how", versions={}
    )
    run(tmp_path, "open", "--root", tree_root)
    last = session_log.last_session_opened_at(cache(tmp_path))
    assert judgments.judgments_since(cache(tmp_path), last) == []


def test_open_with_nothing_waiting_opens_no_issue(tmp_path, gh, capsys):
    root = tmp_path / "product"
    write_node(root, "goal-a", "goal")
    assert run(tmp_path, "open", "--root", root) == 0
    assert "no session opened" in capsys.readouterr().out
    assert not [call for call in gh.calls() if "POST" in call]


def test_dry_run_prints_the_body_and_touches_nothing(tmp_path, tree_root, gh, capsys):
    assert run(tmp_path, "open", "--root", tree_root, "--dry-run") == 0
    assert "Questions of what" in capsys.readouterr().out
    assert gh.calls() == []


def session_issue(tree_root):
    return render_session_body(build_batch(load_tree(tree_root), []))


def route_session(gh, tree_root, *owner_comments, stranger_comment="1: no, rather hijacked"):
    gh.set_route("=repos/acme/widgets/issues/5", {"body": session_issue(tree_root)})
    rows = [
        {"user": {"login": OWNER_LOGIN}, "created_at": f"2026-10-07T10:0{i}:00Z", "body": text}
        for i, text in enumerate(owner_comments)
    ]
    rows.append(
        {
            "user": {"login": "some-agent"},
            "created_at": "2026-10-07T11:00:00Z",
            "body": stranger_comment,
        }
    )
    gh.set_route("issues/5/comments", rows)


def test_answers_reads_only_the_owners_comments(tmp_path, tree_root, gh, capsys):
    route_session(gh, tree_root, "1: no, rather oldest first")
    assert run(tmp_path, "answers", 5) == 0
    out = capsys.readouterr().out
    assert "1. fr-a: answered: oldest first" in out and "hijacked" not in out


def test_answers_on_an_issue_that_is_not_a_session_is_refused(tmp_path, gh, capsys):
    gh.set_route("=repos/acme/widgets/issues/5", {"body": "just an issue"})
    assert run(tmp_path, "answers", 5) == 1
    assert "not a question session" in capsys.readouterr().err


def test_apply_writes_the_answer_into_the_node_and_the_reclaim_outcome_into_the_log(
    tmp_path, tree_root, gh
):
    judgment_id = judgments.record_judgment(
        cache(tmp_path),
        role="refiner",
        kind="soft",
        node="goal-a",
        decision="Weekly view.",
        scope="what",
        versions={},
    )
    body = render_session_body(
        build_batch(
            load_tree(tree_root),
            [
                {
                    "judgment_id": judgment_id,
                    "role": "refiner",
                    "kind": "soft",
                    "node": "fr-a",
                    "decision": "Weekly view.",
                }
            ],
        )
    )
    gh.set_route("=repos/acme/widgets/issues/5", {"body": body})
    gh.set_route(
        "issues/5/comments",
        [
            {
                "user": {"login": OWNER_LOGIN},
                "created_at": "2026-10-07T10:00:00Z",
                "body": "1: yes; reclaim 1",
            }
        ],
    )
    assert run(tmp_path, "apply", 5, "--root", tree_root) == 0
    node = load_tree(tree_root).nodes["fr-a"]
    assert node.experiments[0].outcome == "answered"
    assert node.experiments[0].finding == "newest first"
    assert node.experiments[1].is_open_what_question
    outcomes = judgments.read_outcomes(cache(tmp_path))
    assert [(o["judgment_id"], o["outcome"]) for o in outcomes] == [(judgment_id, "reclaimed")]


def route_pull_request(gh, files, contents):
    gh.set_route("=repos/acme/widgets/pulls/7", {"base": {"sha": "BASE"}, "head": {"sha": "HEAD"}})
    gh.set_route("pulls/7/files", [{"filename": name} for name in files])
    for (side, path), text in contents.items():
        gh.set_route(f"contents/{path}?ref={side}", text)


def test_guard_what_refuses_a_pull_request_that_touches_a_goal(tmp_path, tree_root, gh, capsys):
    goal = (tree_root / "goal-a.md").read_text()
    route_pull_request(
        gh,
        ["product/goal-a.md"],
        {("BASE", "product/goal-a.md"): goal, ("HEAD", "product/goal-a.md"): goal},
    )
    assert run(tmp_path, "guard-what", 7) == 1
    assert "product/goal-a.md: a goal node" in capsys.readouterr().out


def test_guard_what_lets_a_pull_request_on_a_requirement_and_code_through(
    tmp_path, tree_root, gh, capsys
):
    node = (tree_root / "fr-a.md").read_text()
    route_pull_request(
        gh,
        ["product/fr-a.md", "src/app.py"],
        {("BASE", "product/fr-a.md"): node, ("HEAD", "product/fr-a.md"): node},
    )
    assert run(tmp_path, "guard-what", 7) == 0
    assert capsys.readouterr().out == ""


def test_guard_what_reads_the_owner_only_paths_from_the_config(tmp_path, tree_root, gh, capsys):
    route_pull_request(gh, ["eval/battery.yaml"], {})
    assert run(tmp_path, "guard-what", 7, owner_only_paths=["eval/*.yaml"]) == 1
    assert "eval/battery.yaml" in capsys.readouterr().out


def test_verify_answer_accepts_the_exact_transcription_and_refuses_a_stray_edit(
    tmp_path, tree_root, gh, capsys
):
    route_session(gh, tree_root, "1: no, rather oldest first")
    before = (tree_root / "fr-a.md").read_text()
    from agent_os.product.sessions.writeback import answer_question

    answer_question(load_tree(tree_root), "fr-a", QUESTION, "oldest first")
    after = (tree_root / "fr-a.md").read_text()
    contents = {("BASE", "product/fr-a.md"): before, ("HEAD", "product/fr-a.md"): after}
    route_pull_request(gh, ["product/fr-a.md"], contents)
    assert run(tmp_path, "verify-answer", 7, "--session", 5) == 0
    contents[("HEAD", "product/fr-a.md")] = after.replace("oldest first", "oldest first, always")
    route_pull_request(gh, ["product/fr-a.md"], contents)
    assert run(tmp_path, "verify-answer", 7, "--session", 5) == 1
    assert "is not an answer" in capsys.readouterr().out


def test_the_judgment_and_outcome_commands_write_the_log(tmp_path, gh, capsys):
    assert (
        run(
            tmp_path,
            "judgment",
            "--role",
            "refiner",
            "--kind",
            "soft",
            "--decision",
            "Weekly.",
            "--scope",
            "how",
            "--model",
            "m",
        )
        == 0
    )
    judgment_id = capsys.readouterr().out.strip()
    assert run(tmp_path, "outcome", judgment_id, "confirmed", "--source", "pr 3") == 0
    assert (
        json.loads((cache(tmp_path) / "judgments" / "outcomes.jsonl").read_text())["outcome"]
        == "confirmed"
    )
    assert run(tmp_path, "outcome", "j-nope", "confirmed", "--source", "x") == 1
