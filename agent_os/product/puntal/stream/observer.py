"""The stream: what one run's events say, as they arrive."""

from __future__ import annotations

import json

from agent_os.product.puntal.constants import PERSISTENCE_TOOL, STDERR_TAIL_LINES
from agent_os.product.puntal.stream.audit import audit_tool_call
from agent_os.product.puntal.stream.events import (
    Ceilings,
    MessageRecord,
    ToolCall,
    context_tokens,
)


class StreamObserver:
    """Folds one run's stream-json events, in arrival order, into what the telemetry records, and
    says -- from `observe` -- when the run must be cut: a tool call outside the contract, or a
    ceiling passed. Nothing here reads a time: the caller stamps every event."""

    def __init__(self, ceilings: Ceilings, *, tools_allowed: bool = True) -> None:
        self.ceilings = ceilings
        # A fast-path turn is given no tool at all, so any call it makes is outside the contract.
        self.tools_allowed = tools_allowed
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
                call.violation = self._audit(call)
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
                call.violation = self._audit(call)

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

    def _audit(self, call: ToolCall) -> str | None:
        if not self.tools_allowed:
            return f"tool {call.name!r} on a turn that has no tools"
        return audit_tool_call(call.name, call.input)

    def _register_tool_call(
        self, call_id: str | None, name: str | None, tool_input: dict, at_s: float
    ) -> ToolCall:
        call_id = call_id or f"anonymous-{len(self.tool_calls)}"
        if call_id not in self.tool_calls:
            self.tool_calls[call_id] = ToolCall(call_id, name or "", dict(tool_input), at_s)
            if self.first_tool_call_s is None:
                self.first_tool_call_s = at_s
            if not self.tools_allowed:
                self.tool_calls[call_id].violation = f"tool {name!r} on a turn that has no tools"
            elif name != PERSISTENCE_TOOL:
                self.tool_calls[call_id].violation = audit_tool_call(name or "", tool_input)
        return self.tool_calls[call_id]

    # -- what the run has used so far ----------------------------------------------------------
    def peak_context_tokens(self) -> int:
        return max((context_tokens(m.usage) for m in self.messages.values()), default=0)

    def running_total_tokens(self) -> int:
        return sum(
            context_tokens(m.usage) + (m.usage.get("output_tokens") or 0)
            for m in self.messages.values()
        )

    def first_turn_usage(self) -> dict:
        """The four counters of the very first turn, before any tool result existed: what the call
        carried before it did anything -- system prompt, tool definitions, brief -- and, split into
        cache-created, cache-read and uncached, how it was paid for."""
        usage = self.messages[self.message_order[0]].usage if self.message_order else {}
        return {
            name: usage.get(name) or 0
            for name in (
                "input_tokens",
                "cache_creation_input_tokens",
                "cache_read_input_tokens",
                "output_tokens",
            )
        }

    def first_turn_context_tokens(self) -> int:
        """The context floor of the call: what its first turn read. The number the calibration is for."""
        return context_tokens(self.first_turn_usage())

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
