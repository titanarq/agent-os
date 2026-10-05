"""The puntal driver's Python half (Agentos v2, Phase 0): one UI action answered live by one headless
agent process, with everything about the run measured and logged.

A PUNTAL is the shore that props a building up: the product's interface goes live early, every action
is bound to a use case, and an action nobody has implemented yet is answered by this process instead
of by code (`docs/AGENTOS_V2_PLAN.md`). The shell entry is `bin/puntal_task.sh`, a sibling of
`worker_task.sh` that does nothing but start this module under the mechanism's own interpreter, so a
click pays for one Python start-up and not for a chain of `python -m agent_os.lib ...` calls.

    bin/puntal_task.sh --action ACTION --node-file NODE.md [--payload TEXT | --payload-file F]
                       [--state-file F] [--node-id ID] [--session-id S] [--invocation-id ID]
                       [--label KEY=VALUE ...] [--model M] [--effort E] [--timeout SECONDS]
                       [--persistence-command CMD] [--telemetry-file F] [--dry-run]

STDOUT is the response and nothing else -- empty unless the run was answered; diagnostics go to
stderr, and the exit status says how the run ended (0 answered, 1 backend failed, 2 not run, 3 contract
violation, 4 ceiling cut, 124 timeout).
The node slice, the payload and the state are plain text, from a file or from stdin (`-`): this module
knows nothing about the product tree that will one day produce a slice.

THE TELEMETRY RECORD. Every invocation appends exactly one JSON object, on one line, to the telemetry
file (`--telemetry-file`, else `<run dir>/telemetry.jsonl`), whatever its outcome. That file is the
telemetry the refiner will consume to decide which use cases deserve hardening into code, so its shape
is a contract: `TELEMETRY_SCHEMA` is bumped on any incompatible change, and `docs/AGENT_OS.md` §4.6
documents each field. Latencies are seconds from the moment `puntal_task.sh` was entered, which is
the moment the click reaches the driver; `latency_s.first_text_delta` is the time-to-first-signal.

HOW "THE PUNTAL NEVER WRITES CODE" IS ENFORCED -- as far as the `claude` CLI allows, in layers:

1. `--tools Bash`: every other built-in tool (Write, Edit, Read, WebFetch, Task...) is not in the
   model's context at all. `--safe-mode` keeps the user's CLAUDE.md, skills, plugins, hooks and MCP
   servers out of it as well, which is also what keeps the context floor small and reproducible.
2. `--permission-mode dontAsk` with ONE allow rule, `Bash(./state *)`: a call that would ask for
   approval is denied, so the only Bash command that runs is the persistence shim this driver wrote
   into the run's empty scratch directory. The CLI auto-approves read-only commands (`cat`, `ls`)
   whatever the rules say, which is why layers 3 and 4 exist.
3. The stream audit: every `tool_use` is checked as it is assembled, before its result can return
   (`audit_tool_call`): it must be Bash, run `./state`, and carry no shell operator or command
   substitution. The first violation kills the run's process group and the run ends as
   `contract_violation`.
4. The record: every tool call, every violation, every file left in the scratch directory and the
   CLI's own permission denials are written to the telemetry, so "the puntal wrote no code" is a
   query over the log and not a belief.
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import fcntl
import hashlib
import json
import os
import pathlib
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from datetime import UTC, datetime

from agent_os.lib import (
    CONFIG_LOAD_ERRORS,
    HOST_ROOT,
    RUNS_TSV_HEADER,
    ProjectConfig,
    TaskClass,
    backend_config,
    backend_executable,
    config_load_failure,
    load_agents_config,
    load_role_class,
    planner_run_row,
    prompt_extras_path,
    render_prompt,
    write_role_run_exit_marker,
)
from agent_os.streams.claude_jsonl import result_total_tokens, turn_context_tokens

TELEMETRY_SCHEMA = 1
# The top-level keys of one telemetry record, in the order they are written. Documented field by
# field in `docs/AGENT_OS.md` §4.6; a test holds this tuple, the record `build_record` returns and
# that table to the same list.
TELEMETRY_FIELDS = (
    "schema",
    "invocation_id",
    "started_at",
    "action",
    "node",
    "node_digest",
    "session_id",
    "backend_session_id",
    "labels",
    "class",
    "backend",
    "model",
    "effort",
    "outcome",
    "outcome_detail",
    "exit_code",
    "latency_s",
    "usage",
    "cost_usd",
    "tool_calls",
    "tool_violations",
    "init",
    "permission_denials",
    "ceilings",
    "launch",
    "scratch_extra_entries",
    "response",
    "gap_note",
    "stderr_tail",
)
PUNTAL_ROLE = "puntal"

# The one command the puntal may run, and the name of the shim the driver writes for it in the run's
# scratch directory. Short and relative on purpose: the model types it on every call.
STATE_COMMAND = "./state"
SHIM_NAME = "state"
PERSISTENCE_TOOL = "Bash"
# The CLI's permission rule for exactly that command and its arguments.
ALLOW_RULE = f"{PERSISTENCE_TOOL}({STATE_COMMAND} *)"

# The line that ends a response which asked for something its node does not describe.
GAP_MARKER = "GAP:"

# The stream dialect this driver can confine: the flags below are the `claude` CLI's.
SUPPORTED_STREAM = "claude_jsonl"

# Nonessential egress (version checks, telemetry) is start-up latency the person waiting on a click
# should not pay for.
BACKEND_ENVIRONMENT = {"CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"}

EXIT_ANSWERED = 0
EXIT_BACKEND_FAILED = 1
EXIT_NOT_RUN = 2
EXIT_CONTRACT_VIOLATION = 3
EXIT_CEILING_CUT = 4
EXIT_TIMEOUT = 124

OUTCOME_EXIT_STATUS = {
    "ok": EXIT_ANSWERED,
    "error": EXIT_BACKEND_FAILED,
    "contract_violation": EXIT_CONTRACT_VIOLATION,
    "ceiling_cut": EXIT_CEILING_CUT,
    "timeout": EXIT_TIMEOUT,
}

# How long a run that was told to stop gets to leave before it is killed outright.
TERMINATION_GRACE_SECONDS = 3.0
STDERR_TAIL_LINES = 20


class PuntalRefused(Exception):
    """A puntal that cannot be run as configured. Raised before anything is spent or written."""


# ---------------------------------------------------------------------------------------------
# What a puntal may do: the audit of one tool call.
# ---------------------------------------------------------------------------------------------
_SHELL_OPERATOR_CHARACTERS = frozenset("();<>|&")


def audit_tool_call(name: str, tool_input: object) -> str | None:
    """None when this tool call is the one thing a puntal may do -- run `./state` with arguments --
    and otherwise the reason it is not. Deliberately stricter than the CLI's own permission rule: a
    compound command whose every part the CLI would allow is still outside this contract."""
    if name != PERSISTENCE_TOOL:
        return f"tool {name!r} is not the persistence tool"
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or not command.strip():
        return "the Bash call carries no command"
    if "`" in command or "$(" in command or "${" in command or "\n" in command:
        return f"command substitution or a multi-line command: {command[:120]!r}"
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError as error:
        return f"an unparseable command ({error}): {command[:120]!r}"
    if not tokens or tokens[0] != STATE_COMMAND:
        return f"runs something other than {STATE_COMMAND}: {command[:120]!r}"
    for token in tokens:
        if set(token) <= _SHELL_OPERATOR_CHARACTERS:
            return f"a shell operator {token!r}: {command[:120]!r}"
    return None


def split_gap_note(final_text: str) -> tuple[str, str | None]:
    """The response and the gap note a final message carries: the last line that starts with
    `GAP:` is the note, and the rest -- trimmed -- is the response."""
    lines = final_text.strip().split("\n")
    for index in range(len(lines) - 1, -1, -1):
        stripped = lines[index].strip()
        if stripped.startswith(GAP_MARKER):
            note = stripped[len(GAP_MARKER) :].strip()
            response = "\n".join(lines[:index] + lines[index + 1 :]).strip()
            return response, note or None
    return final_text.strip(), None


# ---------------------------------------------------------------------------------------------
# The stream: what one run's events say, as they arrive.
# ---------------------------------------------------------------------------------------------
@dataclasses.dataclass
class ToolCall:
    id: str
    name: str
    input: dict
    first_seen_s: float
    violation: str | None = None
    is_error: bool | None = None
    result_chars: int | None = None


@dataclasses.dataclass
class MessageRecord:
    usage: dict = dataclasses.field(default_factory=dict)
    text_blocks: list[str] = dataclasses.field(default_factory=list)
    first_text_delta_s: float | None = None


@dataclasses.dataclass(frozen=True)
class Ceilings:
    """What binds ONE invocation: the class's three ceilings, the loop guard and the safety timeout."""

    max_context: int
    max_cost_usd: float
    max_total_tokens: int
    max_tool_calls: int
    timeout_seconds: int


def _context_tokens(usage: dict) -> int:
    return turn_context_tokens(usage)


class StreamObserver:
    """Folds one run's stream-json events, in arrival order, into what the telemetry records, and
    says -- from `observe` -- when the run must be cut: a tool call outside the contract, or a
    ceiling passed. Nothing here reads a time: the caller stamps every event."""

    def __init__(self, ceilings: Ceilings) -> None:
        self.ceilings = ceilings
        self.first_event_s: float | None = None
        self.first_message_s: float | None = None
        self.first_tool_call_s: float | None = None
        self.first_text_delta_s: float | None = None
        self.init: dict | None = None
        self.result: dict | None = None
        self.messages: dict[str, MessageRecord] = {}
        self.message_order: list[str] = []
        self.tool_calls: dict[str, ToolCall] = {}
        self.non_event_lines: list[str] = []
        self._current_message: str | None = None
        self._open_tool_blocks: dict[int, dict] = {}

    # -- entry points --------------------------------------------------------------------------
    def observe_line(self, line: str, at_s: float) -> tuple[str, str] | None:
        """One raw stdout line. `(kind, reason)` -- kind `contract_violation` or `ceiling_cut` --
        when the run must be cut, else None. A line that is not JSON is the CLI's own prose (an
        argument error, a stack trace) and is kept for the telemetry's `stderr_tail`."""
        stripped = line.strip()
        if not stripped:
            return None
        if self.first_event_s is None:
            self.first_event_s = at_s
        try:
            event = json.loads(stripped)
        except ValueError:
            self.non_event_lines.append(stripped)
            del self.non_event_lines[:-STDERR_TAIL_LINES]
            return None
        if not isinstance(event, dict):
            return None
        return self.observe(event, at_s)

    def observe(self, event: dict, at_s: float) -> tuple[str, str] | None:
        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "init":
            self.init = event
        elif kind == "stream_event":
            self._observe_partial(event.get("event") or {}, at_s)
        elif kind == "assistant":
            self._observe_assistant(event, at_s)
        elif kind == "user":
            self._observe_tool_results(event)
        elif kind == "result":
            self.result = event
        return self._cut_reason()

    # -- events --------------------------------------------------------------------------------
    def _message(self, message_id: str) -> MessageRecord:
        if message_id not in self.messages:
            self.messages[message_id] = MessageRecord()
            self.message_order.append(message_id)
        return self.messages[message_id]

    def _observe_partial(self, event: dict, at_s: float) -> None:
        kind = event.get("type")
        if kind == "message_start":
            message = event.get("message") or {}
            self._current_message = message.get("id") or f"anonymous-{len(self.message_order)}"
            record = self._message(self._current_message)
            record.usage.update({k: v for k, v in (message.get("usage") or {}).items() if v})
            if self.first_message_s is None:
                self.first_message_s = at_s
        elif kind == "content_block_start":
            block = event.get("content_block") or {}
            if block.get("type") == "tool_use":
                self._register_tool_call(block.get("id"), block.get("name"), {}, at_s)
                self._open_tool_blocks[event.get("index", -1)] = {"id": block.get("id"), "json": ""}
        elif kind == "content_block_delta":
            delta = event.get("delta") or {}
            if delta.get("type") == "text_delta":
                if self.first_text_delta_s is None:
                    self.first_text_delta_s = at_s
                if self._current_message is not None:
                    record = self._message(self._current_message)
                    if record.first_text_delta_s is None:
                        record.first_text_delta_s = at_s
            elif delta.get("type") == "input_json_delta":
                open_block = self._open_tool_blocks.get(event.get("index", -1))
                if open_block is not None:
                    open_block["json"] += delta.get("partial_json") or ""
        elif kind == "content_block_stop":
            open_block = self._open_tool_blocks.pop(event.get("index", -1), None)
            if open_block is not None and open_block["id"] in self.tool_calls:
                try:
                    parsed = json.loads(open_block["json"] or "{}")
                except ValueError:
                    parsed = {}
                call = self.tool_calls[open_block["id"]]
                call.input = parsed if isinstance(parsed, dict) else {}
                call.violation = audit_tool_call(call.name, call.input)
        elif kind == "message_delta":
            if self._current_message is not None:
                usage = event.get("usage") or {}
                self._message(self._current_message).usage.update(
                    {k: v for k, v in usage.items() if v}
                )

    def _observe_assistant(self, event: dict, at_s: float) -> None:
        message = event.get("message")
        if not isinstance(message, dict):
            return
        message_id = message.get("id") or f"anonymous-{len(self.message_order)}"
        record = self._message(message_id)
        if isinstance(message.get("usage"), dict):
            record.usage.update({k: v for k, v in message["usage"].items() if v is not None})
        for block in message.get("content") or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text" and isinstance(block.get("text"), str):
                record.text_blocks.append(block["text"])
            elif block.get("type") == "tool_use":
                call = self._register_tool_call(
                    block.get("id"), block.get("name"), block.get("input") or {}, at_s
                )
                # The complete message is the authority: it replaces what the partial events built.
                call.input = block.get("input") if isinstance(block.get("input"), dict) else {}
                call.violation = audit_tool_call(call.name, call.input)

    def _observe_tool_results(self, event: dict) -> None:
        message = event.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            return
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_result":
                continue
            call = self.tool_calls.get(block.get("tool_use_id"))
            if call is None:
                continue
            call.is_error = bool(block.get("is_error"))
            body = block.get("content")
            call.result_chars = len(body) if isinstance(body, str) else len(json.dumps(body))

    def _register_tool_call(
        self, call_id: str | None, name: str | None, tool_input: dict, at_s: float
    ) -> ToolCall:
        call_id = call_id or f"anonymous-{len(self.tool_calls)}"
        if call_id not in self.tool_calls:
            self.tool_calls[call_id] = ToolCall(call_id, name or "", dict(tool_input), at_s)
            if self.first_tool_call_s is None:
                self.first_tool_call_s = at_s
            if name != PERSISTENCE_TOOL:
                self.tool_calls[call_id].violation = audit_tool_call(name or "", tool_input)
        return self.tool_calls[call_id]

    # -- what the run has used so far ----------------------------------------------------------
    def peak_context_tokens(self) -> int:
        return max((_context_tokens(m.usage) for m in self.messages.values()), default=0)

    def running_total_tokens(self) -> int:
        return sum(
            _context_tokens(m.usage) + (m.usage.get("output_tokens") or 0)
            for m in self.messages.values()
        )

    def violations(self) -> list[str]:
        return [call.violation for call in self.tool_calls.values() if call.violation]

    def _cut_reason(self) -> tuple[str, str] | None:
        violations = self.violations()
        if violations:
            return "contract_violation", violations[0]
        ceilings = self.ceilings
        if len(self.tool_calls) > ceilings.max_tool_calls:
            return "ceiling_cut", f"more than {ceilings.max_tool_calls} tool calls"
        if self.peak_context_tokens() > ceilings.max_context:
            return "ceiling_cut", f"a turn read more than max_context={ceilings.max_context} tokens"
        if self.running_total_tokens() > ceilings.max_total_tokens:
            return "ceiling_cut", f"more than max_total_tokens={ceilings.max_total_tokens} tokens"
        return None

    # -- what the run answered -----------------------------------------------------------------
    def final_message_id(self) -> str | None:
        """The last message that carried text: the one the answer is in."""
        for message_id in reversed(self.message_order):
            record = self.messages[message_id]
            if record.text_blocks or record.first_text_delta_s is not None:
                return message_id
        return None

    def final_text(self) -> str:
        if self.result is not None and not self.result.get("is_error"):
            text = self.result.get("result")
            if isinstance(text, str):
                return text
        message_id = self.final_message_id()
        return "".join(self.messages[message_id].text_blocks) if message_id else ""

    def final_answer_first_delta_s(self) -> float | None:
        message_id = self.final_message_id()
        return self.messages[message_id].first_text_delta_s if message_id else None


# ---------------------------------------------------------------------------------------------
# Launching the backend.
# ---------------------------------------------------------------------------------------------
class Clock:
    """Seconds since `puntal_task.sh` was entered. The shell exports the epoch second it started at
    (`PUNTAL_LAUNCH_EPOCH`), so the interpreter's own start-up and the config load are inside every
    latency instead of invisible to it -- they are part of what the person clicking waits for."""

    def __init__(self, launch_epoch: float | None) -> None:
        self._started = time.monotonic()
        self.overhead_before_python_s = (
            max(0.0, time.time() - launch_epoch) if launch_epoch is not None else 0.0
        )

    def now(self) -> float:
        return self.overhead_before_python_s + (time.monotonic() - self._started)


def backend_flags(*, model: str, effort: str, max_cost_usd: float) -> list[str]:
    """The `claude` command-line flags that confine a puntal, in the order the CLI reads them. The
    options that take a list of values are written `--name=value`: a variadic option followed by a
    space swallows every following argument, the prompt among them."""
    flags = [
        "-p",
        "--output-format",
        "stream-json",
        "--verbose",
        "--include-partial-messages",
        "--safe-mode",
        "--no-session-persistence",
        "--permission-mode",
        "dontAsk",
        f"--tools={PERSISTENCE_TOOL}",
        f"--allowedTools={ALLOW_RULE}",
        "--max-budget-usd",
        f"{max_cost_usd:g}",
        "--model",
        model,
    ]
    if effort:
        flags += ["--effort", effort]
    return flags


def build_brief(*, node_slice: str, action: str, payload: str, relevant_state: str) -> str:
    """What the puntal is told about THIS click: the node slice (it carries its own title), then the
    action, its payload and the state the app passed in. Assembled here, not rendered from the
    template: the payload is a person's text, and running it through placeholder substitution would
    let a payload that contains `__NODE__` rewrite the brief."""
    return (
        f"{node_slice.strip()}\n\n"
        f"# Action\n\n{action}\n\n"
        f"# Payload\n\n{payload.strip() or '(none)'}\n\n"
        f"# State passed in by the app\n\n{relevant_state.strip() or '(none)'}\n"
    )


def backend_executable_for(backend: str, project: ProjectConfig) -> str:
    """`PUNTAL_<BACKEND>_BIN` -- a test's or a bench's override, derived from the name like the other
    drivers' -- else the configured command, else the bare name."""
    variable = "PUNTAL_" + "".join(c if c.isalnum() else "_" for c in backend.upper()) + "_BIN"
    return os.environ.get(variable) or backend_executable(backend, project=project)


def write_state_shim(scratch: pathlib.Path, host_root: pathlib.Path, argv: list[str]) -> None:
    """The puntal's whole tool: `./state ...` in the scratch directory, which runs the app's
    persistence command from the host's root with the arguments it was given."""
    command = list(argv)
    if "/" in command[0] and not os.path.isabs(command[0]):
        command[0] = str(host_root / command[0])
    shim = scratch / SHIM_NAME
    shim.write_text(
        "#!/bin/sh\n"
        f"cd {shlex.quote(str(host_root))} || exit 1\n"
        f'exec {" ".join(shlex.quote(part) for part in command)} "$@"\n'
    )
    shim.chmod(0o755)


@dataclasses.dataclass
class BackendRun:
    exit_code: int | None
    cut: tuple[str, str] | None
    timed_out: bool


def _kill_process_group(process: subprocess.Popen, *, grace: float) -> None:
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(process.pid, signal.SIGKILL)


def run_backend(
    argv: list[str],
    *,
    cwd: pathlib.Path,
    environment: dict[str, str],
    observer: StreamObserver,
    clock: Clock,
    log,
    timeout_seconds: int,
) -> BackendRun:
    """Starts the backend in its own session, folds its stdout into `observer` as it arrives and
    appends every raw line to `log`. The timeout is a watchdog on the whole process group, the one
    safety against a hung process; a cut the observer asks for ends the run as soon as it is seen."""
    process = subprocess.Popen(
        argv,
        cwd=cwd,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        start_new_session=True,
    )
    timed_out = threading.Event()

    def on_timeout() -> None:
        timed_out.set()
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(process.pid, signal.SIGKILL)

    watchdog = threading.Timer(timeout_seconds, on_timeout)
    watchdog.daemon = True
    watchdog.start()
    cut: tuple[str, str] | None = None
    try:
        for line in iter(process.stdout.readline, ""):
            at_s = clock.now()
            log.write(line if line.endswith("\n") else line + "\n")
            log.flush()
            cut = observer.observe_line(line, at_s)
            if cut is not None:
                _kill_process_group(process, grace=TERMINATION_GRACE_SECONDS)
                break
        process.wait()
    finally:
        watchdog.cancel()
        if process.poll() is None:
            _kill_process_group(process, grace=0.0)
        process.stdout.close()
    return BackendRun(process.returncode, cut, timed_out.is_set())


# ---------------------------------------------------------------------------------------------
# The telemetry record.
# ---------------------------------------------------------------------------------------------
def _rounded(value: float | None) -> float | None:
    return None if value is None else round(value, 4)


def _usage_totals(observer: StreamObserver) -> dict:
    """Tokens of the whole run: the terminal `result`'s own aggregate when the run reached one,
    else what the messages seen so far add up to (a cut run has no `result`)."""
    result = observer.result
    if result is not None and isinstance(result.get("usage"), dict):
        usage = result["usage"]
        fields = {
            name: usage.get(name) or 0
            for name in (
                "input_tokens",
                "output_tokens",
                "cache_read_input_tokens",
                "cache_creation_input_tokens",
            )
        }
        total = result_total_tokens(result)
    else:
        fields = {
            name: sum(m.usage.get(name) or 0 for m in observer.messages.values())
            for name in (
                "input_tokens",
                "output_tokens",
                "cache_read_input_tokens",
                "cache_creation_input_tokens",
            )
        }
        total = sum(fields.values())
    return {
        **fields,
        "total_tokens": total,
        "context_tokens_peak": observer.peak_context_tokens(),
        "turns": (result or {}).get("num_turns"),
    }


def ceilings_exceeded(observer: StreamObserver, usage: dict, cost_usd: float | None) -> list[str]:
    ceilings = observer.ceilings
    exceeded = []
    if usage["context_tokens_peak"] > ceilings.max_context:
        exceeded.append("max_context")
    if usage["total_tokens"] > ceilings.max_total_tokens:
        exceeded.append("max_total_tokens")
    if cost_usd is not None and cost_usd > ceilings.max_cost_usd:
        exceeded.append("max_cost_usd")
    if len(observer.tool_calls) > ceilings.max_tool_calls:
        exceeded.append("max_tool_calls")
    return exceeded


def classify_outcome(run: BackendRun, observer: StreamObserver) -> tuple[str, str]:
    """`(outcome, detail)`. The order is the order of what a person waiting must be told: a hung
    run, then a run that broke the contract, then one that ran out of ceiling, then one the CLI
    itself reported as failed."""
    if run.timed_out:
        return "timeout", "the backend produced no result before the safety timeout"
    if run.cut is not None:
        return run.cut
    result = observer.result
    if result is None:
        tail = "; ".join(observer.non_event_lines[-3:])
        return (
            "error",
            f"no result event (exit status {run.exit_code}){': ' + tail if tail else ''}",
        )
    if result.get("subtype") == "error_max_budget_usd":
        return "ceiling_cut", "the CLI stopped the run at --max-budget-usd"
    if result.get("is_error") or run.exit_code not in (0, None):
        detail = result.get("result") if isinstance(result.get("result"), str) else ""
        return (
            "error",
            f"{result.get('subtype') or 'error'} (exit status {run.exit_code}) {detail}"[:400],
        )
    return "ok", ""


def build_record(
    *,
    request: Request,
    options: Options,
    observer: StreamObserver,
    run: BackendRun,
    clock: Clock,
    started_at: datetime,
    scratch_extra: list[str],
    flags: list[str],
    spawned_at_s: float | None,
) -> dict:
    outcome, detail = classify_outcome(run, observer)
    usage = _usage_totals(observer)
    cost = observer.result.get("total_cost_usd") if observer.result else None
    response, gap_note = split_gap_note(observer.final_text())
    init = observer.init or {}
    result = observer.result or {}
    tool_calls = [
        {
            "name": call.name,
            "command": call.input.get("command") if call.name == PERSISTENCE_TOOL else None,
            "at_s": _rounded(call.first_seen_s),
            "violation": call.violation,
            "is_error": call.is_error,
            "result_chars": call.result_chars,
        }
        for call in observer.tool_calls.values()
    ]
    return {
        "schema": TELEMETRY_SCHEMA,
        "invocation_id": request.invocation_id,
        "started_at": started_at.isoformat(timespec="milliseconds"),
        "action": request.action,
        "node": request.node_id,
        "node_digest": "sha256:" + hashlib.sha256(request.node_slice.encode()).hexdigest()[:16],
        "session_id": request.session_id,
        "backend_session_id": result.get("session_id") or init.get("session_id"),
        "labels": request.labels,
        "class": options.class_name,
        "backend": options.backend,
        "model": options.model,
        "effort": options.effort or None,
        "outcome": outcome,
        "outcome_detail": detail,
        "exit_code": run.exit_code,
        "latency_s": {
            "total": _rounded(clock.now()),
            "python_startup": _rounded(clock.overhead_before_python_s),
            "launch_overhead": _rounded(spawned_at_s),
            "first_event": _rounded(observer.first_event_s),
            "first_message": _rounded(observer.first_message_s),
            "first_tool_call": _rounded(observer.first_tool_call_s),
            "first_text_delta": _rounded(observer.first_text_delta_s),
            "final_answer_first_delta": _rounded(observer.final_answer_first_delta_s()),
            "backend_reported": {
                "duration_ms": result.get("duration_ms"),
                "duration_api_ms": result.get("duration_api_ms"),
                "ttft_ms": result.get("ttft_ms"),
            },
        },
        "usage": usage,
        "cost_usd": cost,
        "tool_calls": tool_calls,
        "tool_violations": observer.violations(),
        "init": {
            "tools": init.get("tools"),
            "mcp_servers": init.get("mcp_servers"),
            "permission_mode": init.get("permissionMode"),
            "claude_code_version": init.get("claude_code_version"),
        },
        "permission_denials": len(result.get("permission_denials") or []),
        "ceilings": {
            **dataclasses.asdict(observer.ceilings),
            "exceeded": ceilings_exceeded(observer, usage, cost),
        },
        "launch": {"flags": flags, "persistence_command": options.persistence_command},
        "scratch_extra_entries": scratch_extra,
        "response": response,
        "gap_note": gap_note,
        "stderr_tail": observer.non_event_lines if outcome != "ok" else [],
    }


def append_jsonl(path: pathlib.Path, record: dict) -> None:
    """One line, appended under an exclusive lock: invocations run in parallel (that is the point of
    a puntal) and two records must never interleave."""
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
    with path.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        handle.write(line)
        handle.flush()


def append_runs_row(
    runs_tsv: pathlib.Path, log_path: pathlib.Path, context: str, model: str
) -> None:
    """The class's own `runs.tsv` row, through the helper every role's row goes through."""
    runs_tsv.parent.mkdir(parents=True, exist_ok=True)
    row = planner_run_row(
        log_path.read_text(errors="replace"),
        ts=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        context=context,
        model=model,
    )
    with runs_tsv.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        if os.fstat(handle.fileno()).st_size == 0:
            handle.write(RUNS_TSV_HEADER + "\n")
        handle.write(row + "\n")


# ---------------------------------------------------------------------------------------------
# One invocation, end to end.
# ---------------------------------------------------------------------------------------------
@dataclasses.dataclass(frozen=True)
class Request:
    action: str
    node_id: str
    node_slice: str
    payload: str
    relevant_state: str
    session_id: str
    invocation_id: str
    labels: dict[str, str]


@dataclasses.dataclass(frozen=True)
class Options:
    class_name: str
    backend: str
    model: str
    effort: str
    persistence_command: str
    ceilings: Ceilings
    executable: str
    run_dir: pathlib.Path
    telemetry_file: pathlib.Path
    host_root: pathlib.Path
    contract: str


def run_dir_for(host_root: pathlib.Path) -> pathlib.Path:
    """Where the puntal's per-run logs, `runs.tsv` and default telemetry live: `AGENT_CACHE_DIR`
    whole, exactly as every one-shot role's driver and the guard read it, else `.cache/puntal`."""
    override = os.environ.get("AGENT_CACHE_DIR")
    return pathlib.Path(override) if override else host_root / ".cache" / PUNTAL_ROLE


def resolve_options(
    *, args: argparse.Namespace, clock: Clock, host_root: pathlib.Path
) -> tuple[Options, TaskClass]:
    """Everything config answers, resolved once and refused loudly: a puntal that cannot be run as
    configured must not reach a backend."""
    try:
        config = load_agents_config()
        class_name, task_class = load_role_class(PUNTAL_ROLE)
    except CONFIG_LOAD_ERRORS as error:
        raise PuntalRefused(config_load_failure(error)) from error
    except KeyError as error:
        raise PuntalRefused(str(error.args[0])) from error
    puntal = config.puntal
    backend = backend_config(task_class.backend, project=config.project)
    if backend.stream != SUPPORTED_STREAM:
        raise PuntalRefused(
            f"the puntal class runs on backend '{task_class.backend}', whose stream is "
            f"'{backend.stream}': the tool confinement here is the {SUPPORTED_STREAM} CLI's"
        )
    persistence_command = (
        args.persistence_command
        or os.environ.get("PUNTAL_PERSISTENCE_COMMAND")
        or puntal.persistence_command
    ).strip()
    if not persistence_command:
        raise PuntalRefused(
            "no persistence command: set puntal.persistence_command, PUNTAL_PERSISTENCE_COMMAND or "
            "--persistence-command. State is real from day one (docs/AGENTOS_V2_PLAN.md, founding "
            "decision 4): a puntal that cannot persist contradicts itself between sessions"
        )
    api_text = ""
    if puntal.persistence_api_file:
        api_path = host_root / puntal.persistence_api_file
        if not api_path.is_file():
            raise PuntalRefused(
                f"puntal.persistence_api_file names {api_path}, which is not a file"
            )
        api_text = api_path.read_text()
    try:
        contract = render_prompt(
            PUNTAL_ROLE,
            # The API text goes in first, so that it may use `__STATE_COMMAND__` itself.
            {"PERSISTENCE_API": api_text, "STATE_COMMAND": STATE_COMMAND},
            prompt_extras_path(PUNTAL_ROLE, config.project),
        )
    except (KeyError, FileNotFoundError) as error:
        raise PuntalRefused(str(error.args[0])) from error
    timeout = args.timeout or puntal.timeout_seconds
    run_dir = run_dir_for(host_root)
    options = Options(
        class_name=class_name,
        backend=task_class.backend,
        model=args.model or task_class.model,
        effort=args.effort if args.effort is not None else puntal.effort,
        persistence_command=persistence_command,
        ceilings=Ceilings(
            max_context=task_class.max_context,
            max_cost_usd=task_class.max_cost_usd,
            max_total_tokens=task_class.max_total_tokens,
            max_tool_calls=puntal.max_tool_calls,
            timeout_seconds=timeout,
        ),
        executable=backend_executable_for(task_class.backend, config.project),
        run_dir=run_dir,
        telemetry_file=pathlib.Path(args.telemetry_file)
        if args.telemetry_file
        else run_dir / "telemetry.jsonl",
        host_root=host_root,
        contract=contract,
    )
    return options, task_class


def _read_text(source: str | None, *, what: str) -> str:
    if source is None:
        return ""
    if source == "-":
        return sys.stdin.read()
    path = pathlib.Path(source)
    if not path.is_file():
        raise PuntalRefused(f"{what} {source!r} is not a file")
    return path.read_text()


def build_request(args: argparse.Namespace) -> Request:
    if args.payload is not None and args.payload_file is not None:
        raise PuntalRefused("give the payload with --payload or --payload-file, not both")
    node_slice = _read_text(args.node_file, what="the node file")
    if not node_slice.strip():
        raise PuntalRefused(
            "the node slice is empty: a puntal without a node has no behaviour to follow"
        )
    labels = {}
    for assignment in args.label:
        key, separator, value = assignment.partition("=")
        if not separator or not key:
            raise PuntalRefused(f"--label takes KEY=VALUE, and {assignment!r} is not")
        labels[key] = value
    node_id = args.node_id or (
        pathlib.Path(args.node_file).stem if args.node_file not in (None, "-") else ""
    )
    if not node_id:
        raise PuntalRefused("--node-id is required when the node slice comes from stdin")
    return Request(
        action=args.action,
        node_id=node_id,
        node_slice=node_slice,
        payload=args.payload
        if args.payload is not None
        else _read_text(args.payload_file, what="the payload file"),
        relevant_state=_read_text(args.state_file, what="the state file"),
        session_id=args.session_id or "",
        invocation_id=args.invocation_id or str(uuid.uuid4()),
        labels=labels,
    )


def describe_launch(request: Request, options: Options, flags: list[str], brief: str) -> str:
    return "\n".join(
        [
            f"class:       {options.class_name}",
            f"backend:     {options.backend} ({options.executable})",
            f"model:       {options.model}",
            f"effort:      {options.effort or '(CLI default)'}",
            f"action:      {request.action}",
            f"node:        {request.node_id}",
            f"persistence: {options.persistence_command}",
            f"ceilings:    {dataclasses.asdict(options.ceilings)}",
            f"telemetry:   {options.telemetry_file}",
            f"flags:       {shlex.join(flags)}",
            "--- contract (system prompt) ---",
            options.contract.rstrip("\n"),
            "--- brief (first message) ---",
            brief.rstrip("\n"),
        ]
    )


def invoke(request: Request, options: Options, clock: Clock) -> tuple[dict, str, int]:
    """Runs one puntal and returns `(telemetry record, response text, exit status)`. Writes the
    run's log, its `runs.tsv` row and its telemetry line, whatever the outcome."""
    started_at = datetime.now(UTC)
    flags = backend_flags(
        model=options.model, effort=options.effort, max_cost_usd=options.ceilings.max_cost_usd
    )
    brief = build_brief(
        node_slice=request.node_slice,
        action=request.action,
        payload=request.payload,
        relevant_state=request.relevant_state,
    )
    argv = [options.executable, *flags, "--system-prompt", options.contract, brief]

    options.run_dir.mkdir(parents=True, exist_ok=True)
    stamp = started_at.strftime("%Y%m%dT%H%M%S") + f"-{started_at.microsecond:06d}-{os.getpid()}"
    log_path = options.run_dir / f"{stamp}.log"
    scratch = pathlib.Path(
        tempfile.mkdtemp(prefix="agent-os-puntal-scratch.", dir=os.environ.get("TMPDIR"))
    )
    observer = StreamObserver(options.ceilings)
    try:
        write_state_shim(scratch, options.host_root, shlex.split(options.persistence_command))
        environment = {**os.environ, **BACKEND_ENVIRONMENT}
        with log_path.open("x", encoding="utf-8") as log:
            log.write(
                f"ts:        {stamp}\n"
                f"role:      {PUNTAL_ROLE} (class {options.class_name})\n"
                f"backend:   {options.backend}\n"
                f"model:     {options.model}\n"
                f"action:    {request.action}\n"
                f"node:      {request.node_id}\n"
                f"session:   {request.session_id or '(none)'}\n"
                f"invocation: {request.invocation_id}\n"
            )
            log.flush()
            spawned_at_s = clock.now()
            try:
                run = run_backend(
                    argv,
                    cwd=scratch,
                    environment=environment,
                    observer=observer,
                    clock=clock,
                    log=log,
                    timeout_seconds=options.ceilings.timeout_seconds,
                )
            except OSError as error:
                observer.non_event_lines.append(f"could not start {options.executable}: {error}")
                run = BackendRun(None, None, False)
        scratch_extra = sorted(entry.name for entry in scratch.iterdir() if entry.name != SHIM_NAME)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    # The moment the backend returned, the way every role's driver marks it: the guard dates this
    # run's quota observation by it.
    write_role_run_exit_marker(log_path)
    record = build_record(
        request=request,
        options=options,
        observer=observer,
        run=run,
        clock=clock,
        started_at=started_at,
        scratch_extra=scratch_extra,
        flags=flags,
        spawned_at_s=spawned_at_s,
    )
    append_jsonl(options.telemetry_file, record)
    append_runs_row(
        options.run_dir / "runs.tsv",
        log_path,
        f"{request.action} @ {request.node_id}",
        options.model,
    )
    return record, record["response"], OUTCOME_EXIT_STATUS[record["outcome"]]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="puntal_task.sh",
        description=(__doc__ or "").split("\n\n")[0],
    )
    parser.add_argument("--action", required=True, help="the UI action that was triggered")
    parser.add_argument(
        "--node-file", help="the node slice (use case + ancestor goals); `-` is stdin"
    )
    parser.add_argument("--node-id", help="the node's id (default: the node file's stem)")
    parser.add_argument("--payload", help="the action's payload, as text")
    parser.add_argument("--payload-file", help="the action's payload from a file; `-` is stdin")
    parser.add_argument("--state-file", help="the relevant persisted state the app already holds")
    parser.add_argument("--session-id", help="the app's own session id, recorded in the telemetry")
    parser.add_argument("--invocation-id", help="an id for this invocation (default: a UUID)")
    parser.add_argument("--label", action="append", default=[], metavar="KEY=VALUE")
    parser.add_argument("--model", help="override the puntal class's model")
    parser.add_argument("--effort", default=None, help="override puntal.effort (`claude --effort`)")
    parser.add_argument("--timeout", type=int, default=0, help="override puntal.timeout_seconds")
    parser.add_argument(
        "--persistence-command", default="", help="override the persistence command"
    )
    parser.add_argument("--telemetry-file", help="append the record here, not to the run dir's")
    parser.add_argument("--dry-run", action="store_true", help="print the launch; spend nothing")
    return parser


def main(argv: list[str] | None = None) -> int:
    clock = Clock(
        float(os.environ["PUNTAL_LAUNCH_EPOCH"]) if os.environ.get("PUNTAL_LAUNCH_EPOCH") else None
    )
    args = build_parser().parse_args(argv)
    try:
        if args.node_file is None:
            raise PuntalRefused("--node-file is required (`-` reads the slice from stdin)")
        request = build_request(args)
        options, _task_class = resolve_options(args=args, clock=clock, host_root=HOST_ROOT)
        if args.dry_run:
            flags = backend_flags(
                model=options.model,
                effort=options.effort,
                max_cost_usd=options.ceilings.max_cost_usd,
            )
            brief = build_brief(
                node_slice=request.node_slice,
                action=request.action,
                payload=request.payload,
                relevant_state=request.relevant_state,
            )
            print(describe_launch(request, options, flags, brief))
            return EXIT_ANSWERED
    except PuntalRefused as refusal:
        print(f"puntal not run: {refusal}", file=sys.stderr)
        return EXIT_NOT_RUN
    record, response, status = invoke(request, options, clock)
    if status != EXIT_ANSWERED:
        print(f"puntal {record['outcome']}: {record['outcome_detail']}", file=sys.stderr)
    if record["gap_note"]:
        print(f"puntal gap note: {record['gap_note']}", file=sys.stderr)
    if status == EXIT_ANSWERED:
        # A run that did not finish has no response worth handing the app: what it said before it
        # was cut is in the telemetry and the log, and the exit status says it failed.
        print(response)
    return status


if __name__ == "__main__":
    sys.exit(main())
