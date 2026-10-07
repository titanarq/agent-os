"""Playbook mode of the fake `claude`: a test's exact stream, step by step (see `fake_claude.py`)."""

from __future__ import annotations

import os
import sys
import time


def play_playbook(stream, steps: list[dict]) -> None:
    for step in steps:
        operation = step["op"]
        if operation == "sleep":
            time.sleep(step["seconds"])
        elif operation == "text":
            stream.text(step["text"])
        elif operation == "tool":
            stream.tool(step["command"])
        elif operation == "tool_raw":
            stream.tool_raw(step["name"], step.get("input", {}))
        elif operation == "write_file":
            with open(step["path"], "w") as handle:
                handle.write("written by the fake")
        elif operation == "raw":
            sys.stdout.write(step["line"] + "\n")
            sys.stdout.flush()
        elif operation == "hang":
            time.sleep(3600)
        elif operation == "exit":
            sys.exit(step.get("code", 0))
        elif operation == "final":
            stream.result(
                step["text"],
                subtype=step.get("subtype", "success"),
                is_error=step.get("is_error", False),
            )
            sys.exit(step.get("code", 0))


def next_turn_index(playbook: str, turn_count: int) -> int:
    """Which turn of a multi-turn playbook this process is: how many ran before it, counted in a
    file beside the playbook. Past the last turn, the last one repeats."""
    counter = playbook + ".turn"
    done = 0
    if os.path.exists(counter):
        with open(counter) as handle:
            done = int(handle.read())
    with open(counter, "w") as handle:
        handle.write(str(done + 1))
    return min(done, turn_count - 1)
