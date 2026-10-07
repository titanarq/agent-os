"""The pre-helper: code that loads, before the model runs, the state a node declares its action reads.

A node declares it in its frontmatter, as `reads:` -- a list of read commands of the app's
persistence API, written without the command itself, each one a string:

    reads:
      - list tickets
      - get tickets {payload.id}

`{payload.NAME}` (dots reach into nested objects) is replaced by that field of the click's JSON
payload AFTER the command is split into words, so a value is one argument whatever it contains and
no shell ever sees it. The reads run in parallel through the persistence command, and their output
is the brief's `State loaded for this action`: the model spends no turn reading.

Everything here is tolerant on purpose. A declaration that is malformed, a payload field that is
missing, a read that fails: none stops the click. Each is reported, and shown to the model as what it
is, because the fast path's fallback is the slow path and a slow click beats a failed one.
"""

from __future__ import annotations

import dataclasses
import json
import os
import pathlib
import re
import shlex
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor

import yaml

DECLARATION_KEY = "reads"
FRONTMATTER = re.compile(r"\A---[ \t]*\n(.*?\n)---[ \t]*(?:\n|\Z)", re.DOTALL)
PAYLOAD_FIELD = re.compile(r"\{payload\.([A-Za-z0-9_.-]+)\}")
# A read's output is context the model pays for on every turn: a store that answers with a whole
# collection must not blow the class's ceiling.
MAX_READ_CHARS = 20000


@dataclasses.dataclass(frozen=True)
class NodeDeclaration:
    slice_text: str
    reads: list[str]
    problems: list[str]


@dataclasses.dataclass(frozen=True)
class LoadedState:
    text: str
    declared: int
    ran: int
    failed: int
    duration_s: float
    problems: list[str]
    commands: list[str]


def split_node_declaration(node_text: str) -> NodeDeclaration:
    """The node's slice without its frontmatter, and the reads that frontmatter declares. Text
    that has no frontmatter, or frontmatter that is not a mapping, is a slice like any other."""
    matched = FRONTMATTER.match(node_text)
    if matched is None:
        return NodeDeclaration(node_text, [], [])
    try:
        frontmatter = yaml.safe_load(matched.group(1))
    except yaml.YAMLError as error:
        return NodeDeclaration(
            node_text[matched.end() :], [], [f"the node's frontmatter is not YAML ({error})"]
        )
    if not isinstance(frontmatter, dict):
        return NodeDeclaration(node_text, [], [])
    slice_text = node_text[matched.end() :]
    declared = frontmatter.get(DECLARATION_KEY)
    if declared is None:
        return NodeDeclaration(slice_text, [], [])
    if not isinstance(declared, list) or not all(isinstance(item, str) for item in declared):
        return NodeDeclaration(
            slice_text, [], [f"`{DECLARATION_KEY}` must be a list of read commands (strings)"]
        )
    return NodeDeclaration(slice_text, [item.strip() for item in declared], [])


def _payload_object(payload_text: str) -> dict | None:
    try:
        payload = json.loads(payload_text) if payload_text.strip() else {}
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def _payload_value(payload: dict | None, dotted: str) -> str:
    if payload is None:
        raise KeyError("the payload is not a JSON object")
    value: object = payload
    for part in dotted.split("."):
        if not isinstance(value, dict) or part not in value:
            raise KeyError(f"payload has no {dotted!r}")
        value = value[part]
    if isinstance(value, dict | list) or value is None:
        raise KeyError(f"payload field {dotted!r} is not a single value")
    return str(value)


def _words_of(read: str, payload: dict | None, allowed: tuple[str, ...]) -> list[str]:
    """The read as the words to hand the persistence command, or a KeyError saying why it cannot be."""
    try:
        words = shlex.split(read)
    except ValueError as error:
        raise KeyError(f"unparseable ({error})") from None
    if not words:
        raise KeyError("an empty read")
    if words[0] not in allowed:
        raise KeyError(f"{words[0]!r} is not a read (allowed: {', '.join(allowed)})")
    return [
        PAYLOAD_FIELD.sub(lambda m: _payload_value(payload, m.group(1)), word) for word in words
    ]


def _run_read(argv: list[str], host_root: pathlib.Path, timeout_seconds: int) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            argv,
            cwd=host_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return False, f"failed (no answer within {timeout_seconds}s)"
    except OSError as error:
        return False, f"failed (could not start: {error})"
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        return False, f"failed (exit status {completed.returncode}): {detail}"
    output = completed.stdout.strip()
    if len(output) > MAX_READ_CHARS:
        output = output[:MAX_READ_CHARS] + f"\n... (cut at {MAX_READ_CHARS} characters)"
    return True, output


def load_declared_state(
    reads: list[str],
    *,
    payload_text: str,
    persistence_command: list[str],
    allowed_subcommands: tuple[str, ...],
    host_root: pathlib.Path,
    timeout_seconds: int,
) -> LoadedState:
    started = time.monotonic()
    payload = _payload_object(payload_text)
    command = list(persistence_command)
    if "/" in command[0] and not os.path.isabs(command[0]):
        command[0] = str(host_root / command[0])
    problems: list[str] = []
    runnable: list[tuple[str, list[str]]] = []
    outcomes: dict[str, str] = {}
    for read in reads:
        try:
            # What the model sees is the command as it was really run, the payload's values in it.
            words = _words_of(read, payload, allowed_subcommands)
            runnable.append((shlex.join(words), words))
            outcomes[shlex.join(words)] = ""  # holds the read's place until it has run
        except KeyError as error:
            problems.append(f"read {read!r} skipped: {error.args[0]}")
            outcomes[read] = f"skipped: {error.args[0]}"
    with ThreadPoolExecutor(max_workers=max(1, len(runnable))) as pool:
        futures = [
            (label, pool.submit(_run_read, [*command, *words], host_root, timeout_seconds))
            for label, words in runnable
        ]
        failed_runs = 0
        for label, future in futures:
            succeeded, output = future.result()
            failed_runs += 0 if succeeded else 1
            outcomes[label] = output
    text = "\n\n".join(f"## {label}\n{output}" for label, output in outcomes.items())
    return LoadedState(
        text=text,
        declared=len(reads),
        ran=len(runnable),
        failed=len(reads) - len(runnable) + failed_runs,
        duration_s=round(time.monotonic() - started, 4),
        problems=problems,
        commands=[label for label, _ in runnable],
    )
