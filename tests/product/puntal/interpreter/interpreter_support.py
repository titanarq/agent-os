"""What the interpreter's tests share: the config they run under and how one drives
`bin/interpreter_task.sh` against the puntal's fake `claude` in playbook mode."""

from __future__ import annotations

import json
import os
import subprocess

import pytest

from agent_os.cli import AGENT_OS_DIR

DRIVER = AGENT_OS_DIR / "bin" / "interpreter_task.sh"
FAKE = AGENT_OS_DIR / "bench" / "puntal" / "fake_claude.py"
EXAMPLE_CONFIG = AGENT_OS_DIR / "config.example.yaml"

OWNER_MESSAGE = {
    "text": "The checkbox has no label, the warning is too loud and the box is tiny.",
    "state": "ok_with_improvements",
    "case": "uc-publish-an-ad",
    "page": "/ads/new",
    "at": "2026-10-09T20:30:00Z",
}
CASE = {"id": "uc-publish-an-ad", "title": "Publish an ad", "description": "A seller publishes."}


def request_json(**overrides) -> str:
    document = {
        "thread": [],
        "message": OWNER_MESSAGE,
        "case": CASE,
        "items": [],
        "session_id": "S-1",
        "invocation_id": "inv-1",
    }
    document.update(overrides)
    return json.dumps(document)


def model_answer(**overrides) -> str:
    answer = {"reply": "Understood.", "items": [], "needs_answer": False}
    answer.update(overrides)
    return json.dumps(answer)


def item(kind="change", summary="Label the checkbox", **fields) -> dict:
    return {
        "id": None,
        "kind": kind,
        "summary": summary,
        "node": "uc-publish-an-ad",
        "page": "/ads/new",
        "from_messages": [0],
        **fields,
    }


def play_answers(tmp_path, environment, *answers: str) -> None:
    """One model turn per answer: the first for the first attempt, the next for the retry."""
    playbook = tmp_path / "playbook.json"
    playbook.write_text(json.dumps({"turns": [[{"op": "final", "text": a}] for a in answers]}))
    environment["FAKE_PUNTAL_PLAYBOOK"] = str(playbook)


def interpret(environment, stdin: str, *arguments):
    return subprocess.run(
        ["bash", str(DRIVER), "interpret", *arguments],
        input=stdin,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture(name="environment")
def interpreter_environment(tmp_path, no_real_backend):
    env = dict(os.environ)
    env.update(
        AGENTS_CONFIG_PATH=str(EXAMPLE_CONFIG),
        AGENT_CACHE_DIR=str(tmp_path / "cache"),
        INTERPRETER_CLAUDE_BIN=str(FAKE),
        FAKE_PUNTAL_LATENCY="0",
        FAKE_PUNTAL_STATE_DIR=str(tmp_path / "fake-state"),
        FAKE_PUNTAL_ARGV_LOG=str(tmp_path / "argv.log"),
        FAKE_PUNTAL_PID_FILE=str(tmp_path / "fake.pid"),
    )
    env.pop("FAKE_PUNTAL_FAULT", None)
    env.pop("FAKE_PUNTAL_PLAYBOOK", None)
    return env
