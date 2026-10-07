"""The executor's interface: how a validated plan reaches the app, and what comes back.

The puntal plans and code executes. The operations are the app's to apply -- through its own API,
in its own stack, atomically -- and the app is the only one that knows what a new id is and which
data it derives from what was written. agent-os therefore defines the shape of the operations
(`operations.py`), validates it, and calls the app's EXECUTOR once, here:

    <executor command>            reads  {"operations": [...]}  on stdin
                                  prints {"ok": true,  "bindings": {"<name>": <value>, ...}}
                                      or {"ok": false, "errors": ["<what cannot be applied>", ...]}
                                  on stdout, and exits 0 either way

`ok: true` means every operation was applied; `bindings` holds one value per `allocate` operation,
which agent-os puts into the answer. `ok: false` means NOTHING was applied (the executor is atomic)
and `errors` say why, in words the puntal can act on: they go back to it for ONE retry turn. Any
other end -- a non-zero exit, output that is not that JSON, a timeout -- is a crash, which is not
retried: nothing says what was applied. A host that applies operations in its own process (not
through a command) asks the driver for the plan alone (`puntal_task.sh --json --plan-only`).

`reference_executor.py` interprets the operations over any store with five small methods; the
bench's `executor.py` is that over its JSON document store.
"""

from __future__ import annotations

import dataclasses
import json
import os
import pathlib
import shlex
import subprocess


@dataclasses.dataclass(frozen=True)
class ExecutorVerdict:
    ok: bool
    bindings: dict
    errors: list[str]
    crashed: bool


def resolve_executor_command(command: str, host_root: pathlib.Path) -> list[str]:
    """The executor command as an argument vector, a relative script path taken from the host's root."""
    words = shlex.split(command)
    if "/" in words[0] and not os.path.isabs(words[0]):
        words[0] = str(host_root / words[0])
    return words


def _crash(reason: str) -> ExecutorVerdict:
    return ExecutorVerdict(ok=False, bindings={}, errors=[reason], crashed=True)


def run_executor(command: list[str], operations: list, *, timeout_seconds: int) -> ExecutorVerdict:
    """Runs the app's executor on `operations` and reads its verdict. Never raises: whatever goes
    wrong is a crashed verdict, so the caller has one shape to handle."""
    try:
        completed = subprocess.run(
            command,
            input=json.dumps({"operations": operations}),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return _crash(f"the executor did not answer within {timeout_seconds}s")
    except OSError as error:
        return _crash(f"the executor could not be started: {error}")
    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout).strip()[-300:]
        return _crash(f"the executor exited with status {completed.returncode}: {tail}")
    try:
        verdict = json.loads(completed.stdout)
    except ValueError:
        return _crash(f"the executor's output is not JSON: {completed.stdout.strip()[:200]!r}")
    if not isinstance(verdict, dict) or not isinstance(verdict.get("ok"), bool):
        return _crash(
            f"the executor's output has no boolean `ok`: {completed.stdout.strip()[:200]!r}"
        )
    errors = verdict.get("errors") if isinstance(verdict.get("errors"), list) else []
    bindings = verdict.get("bindings") if isinstance(verdict.get("bindings"), dict) else {}
    if not verdict["ok"] and not errors:
        return _crash("the executor refused the plan and gave no reason")
    return ExecutorVerdict(
        ok=verdict["ok"], bindings=bindings, errors=[str(error) for error in errors], crashed=False
    )
