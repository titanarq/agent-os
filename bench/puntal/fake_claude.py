#!/usr/bin/env python3
"""A stand-in for the `claude` CLI, for the puntal driver's tests and the bench's `--dry-run`.

It never opens a network connection and never spends a token. It accepts exactly the flags
`agent_os.product.puntal.backend_flags` passes (an unknown option is an error, as the real CLI's is, so a
driver that drifts from the CLI's vocabulary fails a test and not a measurement), and it writes the
same stream-json a real `claude -p --output-format stream-json --verbose --include-partial-messages`
run writes: `system/init`, `stream_event`s with text and tool-input deltas, `assistant` messages,
`user` tool results and a terminal `result`.

Two modes, chosen by the environment:

- DOMAIN MODE (default): it plays a perfect puntal for the bench's helpdesk domain. It reads the
  `# Action` and `# Payload` of the brief, then does what the node says through `./state` -- the same
  shim, in the same working directory, a real run would use -- so the store, the shim, the oracle and
  the summary are exercised end to end. `FAKE_PUNTAL_FAULT=<name>` makes it misbehave the way a
  real puntal might, so the checks can be shown to catch it: see `FAULTS`.
- PLAYBOOK MODE (`FAKE_PUNTAL_PLAYBOOK=<json file>`): a list of `{"op": ...}` steps, for a test that
  needs one exact stream: `text`, `tool`, `tool_raw`, `raw`, `write_file`, `sleep`, `final`, `exit`, `hang`.

Other environment: `FAKE_PUNTAL_PID_FILE` (where it writes its pid, so a test can prove it was
killed), `FAKE_PUNTAL_ARGV_LOG` (a file each invocation appends its argv and cwd to),
`FAKE_PUNTAL_LATENCY` (seconds the fake waits between events, default 0.02), `FAKE_PUNTAL_STATE_DIR`
(where it remembers that its prompt cache is warm: the first call there is cold).
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import domain

VALUE_FLAGS = {
    "--output-format",
    "--permission-mode",
    "--max-budget-usd",
    "--model",
    "--effort",
    "--system-prompt",
}
BOOLEAN_FLAGS = {
    "-p",
    "--verbose",
    "--include-partial-messages",
    "--safe-mode",
    "--no-session-persistence",
}
EQUALS_FLAGS = {"--tools", "--allowedTools"}

# What `FAKE_PUNTAL_FAULT` can be, and the action each one afflicts.
FAULTS = {
    "reuse_last_id": "create_ticket: files the new ticket under the previous ticket's id",
    "stale_summary": "create_ticket: does not recount summary/board",
    "accept_invalid_transition": "change_status: moves a ticket whatever its status",
    "lose_ticket": "show_board: deletes T-1 on the way (a read that writes)",
    "wrong_count": "board_report: reports one open ticket too many",
    "no_gap_note": "export_csv: improvises the export and forgets the GAP line",
    "write_code": "export_csv: reaches for a file-writing tool",
    "runaway_context": "any action: a first turn whose context is far past the class's ceiling",
    "hang": "any action: never answers",
    "crash": "any action: dies at start-up with an error and no stream",
    "deny_tool": "calibrate_tool: the CLI denies the persistence tool (the allow rule did not match)",
}

CONTEXT_FLOOR_TOKENS = 5200
INPUT_PRICE, CACHE_WRITE_PRICE, CACHE_READ_PRICE, OUTPUT_PRICE = 3.0, 3.75, 0.3, 15.0


def parse_arguments(argv: list[str]) -> dict:
    """The CLI's own grammar for the flags this driver uses; anything else is an error."""
    parsed: dict = {"flags": {}, "prompt": None}
    index = 0
    while index < len(argv):
        argument = argv[index]
        name, equals, inline = argument.partition("=")
        if name in EQUALS_FLAGS and equals:
            parsed["flags"][name] = inline
        elif argument in VALUE_FLAGS and index + 1 < len(argv):
            index += 1
            parsed["flags"][argument] = argv[index]
        elif argument in BOOLEAN_FLAGS:
            parsed["flags"][argument] = True
        elif argument.startswith("-"):
            print(f"error: unknown option '{argument}'", file=sys.stderr)
            sys.exit(1)
        elif parsed["prompt"] is None:
            parsed["prompt"] = argument
        else:
            print(f"error: too many arguments: {argument!r}", file=sys.stderr)
            sys.exit(1)
        index += 1
    return parsed


class Stream:
    """Writes the events of one run, in the order and with the shapes the real CLI does."""

    def __init__(self, model: str, brief: str, latency: float, cold: bool) -> None:
        self.model, self.latency = model, latency
        self.session_id = f"fake-{uuid.uuid4()}"
        self.message_count = 0
        self.cold = cold
        self.brief_tokens = max(1, len(brief) // 4)
        self.totals = {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        }
        self.started = time.monotonic()
        self.first_context_override: int | None = None
        self.denials: list[dict] = []

    def _emit(self, event: dict) -> None:
        sys.stdout.write(json.dumps(event) + "\n")
        sys.stdout.flush()

    def pause(self, scale: float = 1.0) -> None:
        if self.latency > 0:
            time.sleep(self.latency * scale)

    def init(self) -> None:
        self.pause(2)
        self._emit(
            {
                "type": "system",
                "subtype": "init",
                "session_id": self.session_id,
                "cwd": os.getcwd(),
                "tools": ["Bash"],
                "mcp_servers": [],
                "model": self.model,
                "permissionMode": "dontAsk",
                "claude_code_version": "fake-0",
            }
        )

    def _usage(self, output_tokens: int) -> dict:
        """A turn's counters as the real CLI shapes them: the first turn pays for the brief as new
        input on top of the cached system prompt and tool definitions; every later turn reads all of
        that from the cache and adds only the last tool result, so the context grows turn by turn."""
        turn = self.message_count
        if turn == 0:
            cached = self.first_context_override or CONTEXT_FLOOR_TOKENS
            fresh = 40 + self.brief_tokens
        else:
            cached = CONTEXT_FLOOR_TOKENS + self.brief_tokens + 40 + (turn - 1) * 180
            fresh = 120
        creating = self.cold and turn == 0
        usage = {
            "input_tokens": fresh,
            "cache_creation_input_tokens": cached if creating else 0,
            "cache_read_input_tokens": 0 if creating else cached,
            "output_tokens": output_tokens,
        }
        for key, value in usage.items():
            self.totals[key] += value
        return usage

    def _message(self, blocks: list[dict]) -> None:
        """One assistant message made of `blocks` (text and/or tool_use), streamed then completed."""
        self.pause(3)
        message_id = f"msg_fake_{self.message_count}"
        output_tokens = sum(len(json.dumps(b)) // 4 + 4 for b in blocks)
        usage = self._usage(output_tokens)
        self._emit(
            {
                "type": "stream_event",
                "event": {
                    "type": "message_start",
                    "message": {
                        "id": message_id,
                        "role": "assistant",
                        "content": [],
                        "usage": {**usage, "output_tokens": 1},
                    },
                },
            }
        )
        for index, block in enumerate(blocks):
            if block["type"] == "text":
                self._emit(
                    {
                        "type": "stream_event",
                        "event": {
                            "type": "content_block_start",
                            "index": index,
                            "content_block": {"type": "text", "text": ""},
                        },
                    }
                )
                text = block["text"]
                for start in range(0, max(len(text), 1), 16):
                    self.pause(0.5)
                    self._emit(
                        {
                            "type": "stream_event",
                            "event": {
                                "type": "content_block_delta",
                                "index": index,
                                "delta": {"type": "text_delta", "text": text[start : start + 16]},
                            },
                        }
                    )
            else:
                self._emit(
                    {
                        "type": "stream_event",
                        "event": {
                            "type": "content_block_start",
                            "index": index,
                            "content_block": {
                                "type": "tool_use",
                                "id": block["id"],
                                "name": block["name"],
                                "input": {},
                            },
                        },
                    }
                )
                encoded = json.dumps(block["input"])
                for start in range(0, len(encoded), 24):
                    self._emit(
                        {
                            "type": "stream_event",
                            "event": {
                                "type": "content_block_delta",
                                "index": index,
                                "delta": {
                                    "type": "input_json_delta",
                                    "partial_json": encoded[start : start + 24],
                                },
                            },
                        }
                    )
            self._emit(
                {"type": "stream_event", "event": {"type": "content_block_stop", "index": index}}
            )
        stop = "tool_use" if any(b["type"] == "tool_use" for b in blocks) else "end_turn"
        self._emit(
            {
                "type": "stream_event",
                "event": {
                    "type": "message_delta",
                    "delta": {"stop_reason": stop},
                    "usage": {"output_tokens": output_tokens},
                },
            }
        )
        self._emit({"type": "stream_event", "event": {"type": "message_stop"}})
        for block in blocks:
            self._emit(
                {
                    "type": "assistant",
                    "message": {
                        "id": message_id,
                        "role": "assistant",
                        "model": self.model,
                        "content": [block],
                        "usage": usage,
                    },
                    "session_id": self.session_id,
                }
            )
        self.message_count += 1

    def text(self, text: str) -> None:
        self._message([{"type": "text", "text": text}])

    def tool(self, command: str, *, deny: bool = False) -> tuple[str, bool]:
        """A Bash tool call, executed for real in the working directory (where `./state` is), or
        denied the way the CLI denies a call that no allow rule matches."""
        tool_id = f"toolu_fake_{self.message_count}"
        self._message(
            [{"type": "tool_use", "id": tool_id, "name": "Bash", "input": {"command": command}}]
        )
        if deny:
            output, failed = "Permission to use Bash with this command was denied", True
            self.denials.append({"tool_name": "Bash", "tool_use_id": tool_id})
        else:
            completed = subprocess.run(
                command, shell=True, capture_output=True, text=True, check=False
            )
            failed = completed.returncode != 0
            output = completed.stderr if failed else completed.stdout
        self._emit(
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": output,
                            "is_error": failed,
                        }
                    ],
                },
                "session_id": self.session_id,
            }
        )
        return output, failed

    def tool_raw(self, name: str, tool_input: dict) -> None:
        self._message(
            [
                {
                    "type": "tool_use",
                    "id": f"toolu_fake_{self.message_count}",
                    "name": name,
                    "input": tool_input,
                }
            ]
        )

    def result(self, final_text: str, *, subtype: str = "success", is_error: bool = False) -> None:
        self.pause(1)
        self.text(final_text) if not is_error else None
        cost = (
            self.totals["input_tokens"] * INPUT_PRICE
            + self.totals["cache_creation_input_tokens"] * CACHE_WRITE_PRICE
            + self.totals["cache_read_input_tokens"] * CACHE_READ_PRICE
            + self.totals["output_tokens"] * OUTPUT_PRICE
        ) / 1_000_000
        elapsed_ms = int((time.monotonic() - self.started) * 1000)
        self._emit(
            {
                "type": "result",
                "subtype": subtype,
                "is_error": is_error,
                "duration_ms": elapsed_ms,
                "duration_api_ms": int(elapsed_ms * 0.8),
                "num_turns": self.message_count,
                "result": final_text,
                "session_id": self.session_id,
                "total_cost_usd": round(cost, 6),
                "usage": dict(self.totals),
                "modelUsage": {},
                "permission_denials": self.denials,
            }
        )


# ---------------------------------------------------------------------------------------------
# Domain mode: a perfect puntal for the helpdesk, with optional faults.
# ---------------------------------------------------------------------------------------------
def _json_of(output: str) -> object:
    return json.loads(output)


def _put(stream: Stream, collection: str, identifier: str, document: dict) -> None:
    stream.tool(f"./state put {collection} {identifier} {shlex.quote(json.dumps(document))}")


def _recount_and_store(stream: Stream) -> None:
    tickets = _json_of(stream.tool("./state list tickets")[0])
    counts = {
        status: sum(1 for t in tickets if t["status"] == status) for status in domain.STATUSES
    }
    _put(stream, "summary", "board", {**counts, "total": len(tickets)})


def play_domain(stream: Stream, action: str, payload: dict, fault: str) -> str:
    if action == "calibrate":
        return '{"ok": true}'
    if action == "calibrate_tool":
        stream.tool("./state list tickets", deny=fault == "deny_tool")
        return '{"ok": true}'
    if action == "create_ticket":
        ticket_id = None
        if fault == "reuse_last_id":
            existing = _json_of(stream.tool("./state list tickets")[0])
            ticket_id = existing[-1]["id"] if existing else None
        if ticket_id is None:
            ticket_id = f"T-{_json_of(stream.tool('./state next-id ticket')[0])}"
        _put(
            stream,
            "tickets",
            ticket_id,
            {
                "id": ticket_id,
                "title": str(payload.get("title", "")).strip(),
                "priority": payload.get("priority") or "normal",
                "status": "open",
                "resolution": None,
            },
        )
        if fault != "stale_summary":
            _recount_and_store(stream)
        return json.dumps({"ok": True, "ticket_id": ticket_id})
    if action == "change_status":
        ticket_id, target = str(payload.get("id", "")), payload.get("status")
        note = str(payload.get("note") or "").strip()
        output, failed = stream.tool(f"./state get tickets {shlex.quote(ticket_id)}")
        refusal = None
        if failed:
            refusal = "no such ticket"
        else:
            ticket = _json_of(output)
            if (
                fault != "accept_invalid_transition"
                and domain.NEXT_STATUS.get(ticket["status"]) != target
            ):
                refusal = f"a {ticket['status']} ticket cannot become {target}"
            elif target == "resolved" and not note:
                refusal = "a resolved ticket needs a note"
        if refusal:
            return json.dumps({"ok": False, "ticket_id": ticket_id, "reason": refusal})
        changes = {"status": target, "resolution": note if target == "resolved" else None}
        stream.tool(
            f"./state update tickets {shlex.quote(ticket_id)} {shlex.quote(json.dumps(changes))}"
        )
        _recount_and_store(stream)
        return json.dumps({"ok": True, "ticket_id": ticket_id, "status": target})
    if action in ("show_board", "board_report", "export_csv"):
        if fault == "lose_ticket" and action == "show_board":
            stream.tool("./state delete tickets T-1")
        if fault == "write_code" and action == "export_csv":
            stream.tool_raw("Write", {"file_path": "export.py", "content": "print('csv')"})
        tickets = _json_of(stream.tool("./state list tickets")[0])
        counts = {
            status: sum(1 for t in tickets if t["status"] == status) for status in domain.STATUSES
        }
        if action == "show_board":
            board = [{k: t[k] for k in ("id", "title", "priority", "status")} for t in tickets]
            return json.dumps({"tickets": board, "counts": {**counts, "total": len(tickets)}})
        if action == "board_report":
            unresolved = [t for t in tickets if t["status"] != "resolved"]
            reported = dict(counts)
            if fault == "wrong_count":
                reported["open"] += 1
            return json.dumps(
                {
                    "total": len(tickets),
                    "counts": reported,
                    "oldest_unresolved": unresolved[0]["id"] if unresolved else None,
                    "high_priority_unresolved": [
                        t["id"] for t in unresolved if t["priority"] == "high"
                    ],
                }
            )
        rows = ["id,title,priority,status"] + [
            f'{t["id"]},"{t["title"]}",{t["priority"]},{t["status"]}' for t in tickets
        ]
        text = "\n".join(rows)
        return (
            text
            if fault == "no_gap_note"
            else text + "\nGAP: asked for a CSV export; the node does not describe it"
        )
    return json.dumps({"ok": False, "reason": f"unknown action {action}"})


def play_playbook(stream: Stream, steps: list[dict]) -> None:
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


def section(brief: str, heading: str) -> str:
    start = brief.find(f"# {heading}\n")
    if start < 0:
        return ""
    body = brief[start + len(heading) + 3 :]
    end = body.find("\n# ")
    return (body if end < 0 else body[:end]).strip()


def main() -> int:
    arguments = parse_arguments(sys.argv[1:])
    if os.environ.get("FAKE_PUNTAL_ARGV_LOG"):
        with open(os.environ["FAKE_PUNTAL_ARGV_LOG"], "a") as log:
            log.write(
                json.dumps(
                    {
                        "argv": sys.argv[1:],
                        "cwd": os.getcwd(),
                        "environment": {
                            k: v for k, v in os.environ.items() if k.startswith("CLAUDE_CODE_")
                        },
                    }
                )
                + "\n"
            )
    if os.environ.get("FAKE_PUNTAL_PID_FILE"):
        with open(os.environ["FAKE_PUNTAL_PID_FILE"], "w") as handle:
            handle.write(str(os.getpid()))
    brief = arguments["prompt"] or ""
    flags = arguments["flags"]
    state_dir = os.environ.get("FAKE_PUNTAL_STATE_DIR")
    cold = False
    if state_dir:
        os.makedirs(state_dir, exist_ok=True)
        marker = os.path.join(state_dir, "cache-is-warm")
        cold = not os.path.exists(marker)
        open(marker, "a").close()
    stream = Stream(
        str(flags.get("--model", "fake-model")),
        brief + str(flags.get("--system-prompt", "")),
        float(os.environ.get("FAKE_PUNTAL_LATENCY", "0.02")),
        cold,
    )
    fault = os.environ.get("FAKE_PUNTAL_FAULT", "")
    if fault == "runaway_context":
        stream.first_context_override = 90000
    if fault == "crash":
        print("error: simulated crash before the first event", file=sys.stderr)
        return 1
    stream.init()
    playbook = os.environ.get("FAKE_PUNTAL_PLAYBOOK")
    if playbook:
        with open(playbook) as handle:
            play_playbook(stream, json.load(handle))
        return 0
    if fault == "hang":
        time.sleep(3600)
    action = section(brief, "Action")
    try:
        payload = json.loads(section(brief, "Payload") or "{}")
    except ValueError:
        payload = {}
    stream.result(play_domain(stream, action, payload if isinstance(payload, dict) else {}, fault))
    return 0


if __name__ == "__main__":
    sys.exit(main())
