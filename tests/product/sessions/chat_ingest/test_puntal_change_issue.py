"""An approved `puntal_change` opens ONE issue on the mechanism's repository (agent-os#183); held when
`sessions.mechanism_repository` is empty, proposed whatever the guard says."""

from __future__ import annotations

import json

import pytest
import yaml
from sessions_support import (
    SESSION,
    ChatTracker,
    chat_comment,
    chat_document,
    chat_item,
    config_file,
    write_node,
)

from agent_os.product.session_ingest import cli as ingest_cli
from agent_os.product.sessions.cli import main

MECHANISM = "someone/mechanism"
VERSIONS = {"model": "m-1", "prompt": "p-1"}
THE_KEY = f"puntal-change.{SESSION}.item-1"


@pytest.fixture
def host(tmp_path, monkeypatch):
    def build(*, repository: str, guard: bool = False):
        root = tmp_path / "product"
        write_node(root, "goal-a", "goal")
        write_node(root, "uc-bad", "use-case", parent="goal-a", state="improvised")
        sessions = tmp_path / "sessions"
        sessions.mkdir()
        config = config_file(
            tmp_path,
            confirm_before_dispatch=guard,
            ticket_budget_class="mechanical-qwen",
            test_sessions_dir=str(sessions),
        )
        data = yaml.safe_load(config.read_text())
        data["sessions"]["mechanism_repository"] = repository
        config.write_text(yaml.safe_dump(data, sort_keys=False))
        host_tracker, mechanism_tracker = ChatTracker(), ChatTracker()
        monkeypatch.setattr(ingest_cli, "build_tracker", lambda: host_tracker)
        monkeypatch.setattr(
            ingest_cli,
            "build_mechanism_tracker",
            lambda repository_name: (
                mechanism_tracker if repository_name == MECHANISM else pytest.fail(repository_name)
            ),
        )
        monkeypatch.setenv("WORKER_CACHE_DIR", str(tmp_path / "cache"))
        monkeypatch.setenv("AGENT_CACHE_DIR", str(tmp_path / "puntal"))
        monkeypatch.setenv("AGENT_OS_HOST_ROOT", str(tmp_path))
        puntal = tmp_path / "puntal"
        puntal.mkdir()
        row = {
            "invocation_id": "inv-1",
            "action": "resend",
            "node": "uc-bad",
            "outcome": "ok",
            "versions": VERSIONS,
        }
        (puntal / "telemetry.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
        return sessions, host_tracker, mechanism_tracker, config

    return build


def write_session(sessions, *, status: str | None, invocations=("inv-1",), withdrawn=False):
    fields = {"status": status} if status else {}
    item = chat_item(
        1,
        "puntal_change",
        "The puntal ignores the red warning the case describes",
        [0],
        node="uc-bad",
        invocations=list(invocations),
        withdrawn=withdrawn,
        **fields,
    )
    document = chat_document(
        [chat_comment("It never shows the red warning")], [], items=[item], questions=[]
    )
    (sessions / "a.json").write_text(json.dumps(document), encoding="utf-8")


def ingest(config, *argv) -> int:
    return main(["test-ingest", *argv], config_path=config)


def test_an_approved_puntal_change_opens_one_issue_on_the_mechanism_with_its_evidence(host):
    sessions, host_tracker, mechanism_tracker, config = host(repository=MECHANISM)
    write_session(sessions, status="approved")
    assert ingest(config, "--apply") == 0
    assert host_tracker.opened == []
    ((title, body, _),) = mechanism_tracker.opened
    assert "Assess the puntal's instructions" in title
    assert f"<!-- key: {THE_KEY} -->" in body
    task = body.split("## Objective")[1].split("## Acceptance criteria")[0]
    assert "prompts/puntal.md" in task and "replay battery" in task and "red warning" not in task
    context = body.split("## Context")[1].split("## Not included")[0]
    assert "inv-1" in context and "resend" in context and '"prompt": "p-1"' in context
    assert "It never shows the red warning" in context
    assert "Changing a goal, a requirement, a use case or an evaluator" in body
    (block,) = json.loads((sessions / "understood.json").read_text())["sessions"]
    assert [(c["origin"], c["issue"]) for c in block["changes"]] == [("puntal change", 101)]


def test_a_second_run_opens_nothing(host):
    sessions, _, mechanism_tracker, config = host(repository=MECHANISM)
    write_session(sessions, status="approved")
    ingest(config, "--apply")
    assert ingest(config, "--apply", "--session", SESSION) == 0
    assert len(mechanism_tracker.opened) == 1


def test_with_no_mechanism_repository_it_is_held_and_listed(host, capsys):
    sessions, host_tracker, mechanism_tracker, config = host(repository="")
    write_session(sessions, status="approved")
    assert ingest(config, "--apply") == 0
    assert "sessions.mechanism_repository` is empty" in capsys.readouterr().out
    assert host_tracker.opened == [] and mechanism_tracker.opened == []
    (block,) = json.loads((sessions / "understood.json").read_text())["sessions"]
    assert [h["node"] for h in block["held"]] == ["uc-bad"] and block["changes"] == []


@pytest.mark.parametrize("guard", [False, True])
@pytest.mark.parametrize("status", ["proposed", None])
def test_it_waits_for_approval_whatever_the_guard_says(host, status, guard):
    sessions, _, mechanism_tracker, config = host(repository=MECHANISM, guard=guard)
    write_session(sessions, status=status)
    assert ingest(config, "--apply") == 0
    assert mechanism_tracker.opened == []
    (block,) = json.loads((sessions / "understood.json").read_text())["sessions"]
    assert [p["id"] for p in block["proposals"]] == ["item-1"]


def test_an_unknown_invocation_is_a_problem_and_opens_nothing(host, capsys):
    sessions, _, mechanism_tracker, config = host(repository=MECHANISM)
    write_session(sessions, status="approved", invocations=("inv-9",))
    assert ingest(config, "--apply") == 1
    assert "no invocation 'inv-9'" in capsys.readouterr().err
    assert mechanism_tracker.opened == []
