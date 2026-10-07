"""What the puntal's driver tests share: where the pieces are, the config they run under and how a
test drives `bin/puntal_task.sh` against the fake `claude`."""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest
import yaml

from agent_os.cli import AGENT_OS_DIR

EXAMPLE_CONFIG = AGENT_OS_DIR / "config.example.yaml"
MULTI_BACKEND_CONFIG = AGENT_OS_DIR / "tests" / "product" / "config" / "multi_backend_config.yaml"
DRIVER = AGENT_OS_DIR / "bin" / "puntal_task.sh"
BENCH = AGENT_OS_DIR / "bench" / "puntal"
FAKE = BENCH / "fake_claude.py"
STORE_CLI = BENCH / "store.py"
EXECUTOR_CLI = BENCH / "executor.py"
NODE_FILE = BENCH / "nodes" / "uc-1-file-a-ticket.md"
BOARD_NODE_FILE = BENCH / "nodes" / "uc-3-see-the-board.md"


def write_config(tmp_path, *, puntal_section=None, puntal_class=None, class_backend=None):
    data = yaml.safe_load(EXAMPLE_CONFIG.read_text())
    if class_backend and class_backend not in data["project"]["backends"]:
        # The shipped example describes one backend; a class on another needs the multi-backend shape.
        data = yaml.safe_load(MULTI_BACKEND_CONFIG.read_text())
    data["puntal"].update(puntal_section or {})
    data["classes"]["puntal"].update(puntal_class or {})
    if class_backend:
        # The example declares one backend; a test that names another registers it first.
        data["project"]["backends"].setdefault(
            class_backend,
            {
                "worktree": f"../example-{class_backend}",
                "app": f"example-{class_backend}",
                "stream": f"{class_backend}_jsonl",
            },
        )
        data["classes"]["puntal"]["backend"] = class_backend
    path = tmp_path / "agents.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return path


def drive(
    environment, *arguments, node=NODE_FILE, action="create_ticket", payload=None, path="slow"
):
    """The driver's SLOW path by default: this file is about the confined tool loop (the shim, the
    audit, the ceilings, the log). The fast path -- plan, executor -- is `test_puntal_fast_path.py`."""
    command = ["bash", str(DRIVER), "--action", action, "--node-file", str(node)]
    if path:
        command += ["--path", path]
    if payload is not None:
        command += ["--payload", json.dumps(payload)]
    return subprocess.run(
        [*command, *arguments], env=environment, capture_output=True, text=True, check=False
    )


def telemetry_of(tmp_path) -> list[dict]:
    path = tmp_path / "cache" / "telemetry.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def play(tmp_path, environment, steps):
    playbook = tmp_path / "playbook.json"
    playbook.write_text(json.dumps(steps))
    environment["FAKE_PUNTAL_PLAYBOOK"] = str(playbook)


@pytest.fixture(name="environment")
def puntal_environment(tmp_path):
    """The driver's launch path with every write moved under tmp_path, the fake as its backend and no
    latency: nothing real is reachable from a run in this fixture. A test module gets it by
    importing `puntal_environment` (a conftest.py here would shadow the suite's own)."""
    env = dict(os.environ)
    env.update(
        AGENTS_CONFIG_PATH=str(write_config(tmp_path)),
        AGENT_CACHE_DIR=str(tmp_path / "cache"),
        PUNTAL_CLAUDE_BIN=str(FAKE),
        PUNTAL_PERSISTENCE_COMMAND=f"{sys.executable} {STORE_CLI} --dir {tmp_path / 'store'}",
        PUNTAL_EXECUTOR_COMMAND=f"{sys.executable} {EXECUTOR_CLI} --dir {tmp_path / 'store'}",
        FAKE_PUNTAL_LATENCY="0",
        FAKE_PUNTAL_STATE_DIR=str(tmp_path / "fake-state"),
        FAKE_PUNTAL_ARGV_LOG=str(tmp_path / "argv.log"),
        FAKE_PUNTAL_PID_FILE=str(tmp_path / "fake.pid"),
    )
    env.pop("FAKE_PUNTAL_FAULT", None)
    env.pop("FAKE_PUNTAL_PLAYBOOK", None)
    return env
