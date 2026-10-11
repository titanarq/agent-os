"""The issue a launched change opens as keeps the task apart from the background: one message of
the owner with a change and four decisions yields a task that is the change alone."""

from __future__ import annotations

import json
import re

import pytest
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

THE_CHANGE = "Show the red warning on the ads list"
THE_DECISIONS = (
    "Cap the ads of an account at ten",
    "Let a deleted ad be recovered for a week",
    "Charge for featured ads",
    "Send a weekly digest by email",
)
THE_OWNERS_MESSAGE = "\n".join(
    [f"1. {THE_CHANGE}"] + [f"{number}. {text}" for number, text in enumerate(THE_DECISIONS, 2)]
)
TRACKED_SEPARATELY = "tracked separately, NOT part of this task"


@pytest.fixture
def opened_issues(tmp_path, monkeypatch) -> list[tuple[str, str, list[str]]]:
    write_node(tmp_path / "product", "goal-a", "goal")
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
    items = [chat_item(1, "change", THE_CHANGE, [0])]
    items += [chat_item(n, "decision", text, [0]) for n, text in enumerate(THE_DECISIONS, 2)]
    items.append(chat_item(6, "question_of_what", "May an ad have a video?", [0]))
    items.append(chat_item(7, "change", "Redo the footer", [0], withdrawn=True))
    items.append(chat_item(8, "change", "Put the euro sign on every price", [1]))
    comments = [chat_comment(THE_OWNERS_MESSAGE), chat_comment("Prices need the euro sign")]
    (sessions / "a.json").write_text(
        json.dumps(chat_document(comments, [], items=items, questions=[])), encoding="utf-8"
    )
    assert main(["test-ingest", "--apply"], config_path=config) == 0
    return tracker.opened


def section(body: str, heading: str) -> str:
    return re.search(rf"^{heading}\n(.*?)(?=^## |\Z)", body, re.MULTILINE | re.DOTALL).group(1)


def body_of_the_change(opened_issues) -> str:
    (body,) = [body for title, body, _ in opened_issues if THE_CHANGE in title]
    return body


def test_the_task_is_the_change_alone(opened_issues):
    task = section(body_of_the_change(opened_issues), "## Objective")
    assert THE_CHANGE in task and "only work this issue asks for" in task
    assert not any(text in task for text in THE_DECISIONS)
    assert "> " not in task


def test_the_owners_whole_message_is_background_and_says_so(opened_issues):
    context = section(body_of_the_change(opened_issues), "## Context")
    assert "background, not part of the task" in context
    assert "> [0] owner (/ads): 1. " + THE_CHANGE in context
    assert all(f"> {line}" in context for line in THE_OWNERS_MESSAGE.splitlines()[1:])
    assert "the messages are right" not in context


def test_every_other_item_of_the_message_is_listed_as_not_included(opened_issues):
    not_included = section(body_of_the_change(opened_issues), "## Not included")
    listed = [line for line in not_included.splitlines() if TRACKED_SEPARATELY in line]
    for summary in (*THE_DECISIONS, "May an ad have a video?"):
        assert [line for line in listed if summary in line], summary
    assert len(listed) == len(THE_DECISIONS) + 1


def test_an_item_withdrawn_or_read_from_another_message_is_not_listed(opened_issues):
    not_included = section(body_of_the_change(opened_issues), "## Not included")
    assert "Redo the footer" not in not_included and "euro sign" not in not_included


def test_the_acceptance_and_the_stages_point_at_the_task_not_at_the_messages(opened_issues):
    body = body_of_the_change(opened_issues)
    for heading in ("## Acceptance criteria", "## Stages"):
        assert "the Task" in section(body, heading) and "messages" not in section(body, heading)


def test_the_markers_the_guard_and_the_planner_read_are_kept(opened_issues):
    body = body_of_the_change(opened_issues)
    assert "<!-- budget: mechanical-qwen -->" in body
    assert f"<!-- key: test-change.{SESSION}.item.item-1 -->" in body
