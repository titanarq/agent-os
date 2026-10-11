"""A worker or validator stops only the processes it started, by the PID it kept.

On the first v2 host a worker's smoke test ended with `pkill -f "python -m app"`, and the owner's own
running web -- another process, another port, in the main checkout -- was dead. The machine is shared
and a pattern cannot tell a smoke server from the product the owner is using, so the rule is in the
prompts of the two roles that run what they check (`AGENTS.md` says the same of this repository).
"""

from __future__ import annotations

import pytest

from agent_os.cli import AGENT_OS_DIR


def prompt_words(role: str) -> str:
    return " ".join((AGENT_OS_DIR / "prompts" / f"{role}.md").read_text().split())


@pytest.mark.parametrize("role", ["worker", "validator"])
def test_the_prompt_stops_what_it_started_by_pid_and_never_by_pattern(role):
    prompt = prompt_words(role)
    assert "PID you kept" in prompt
    for forbidden in ("`pkill`", "`killall`", "`pgrep -f | xargs kill`"):
        assert forbidden in prompt, forbidden


@pytest.mark.parametrize("role", ["worker", "validator"])
def test_the_prompt_never_touches_a_port_it_did_not_open(role):
    assert "never use, free or stop" in prompt_words(role)
    assert "already listening" in prompt_words(role)


def test_the_worker_is_told_how_to_keep_the_pid():
    assert "echo $! > scratchpad/server.pid" in prompt_words("worker")
