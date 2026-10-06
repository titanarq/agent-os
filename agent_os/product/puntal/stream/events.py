"""The values a run's stream is folded into."""

from __future__ import annotations

import dataclasses

from agent_os.streams.claude_jsonl import turn_context_tokens


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


def context_tokens(usage: dict) -> int:
    return turn_context_tokens(usage)
