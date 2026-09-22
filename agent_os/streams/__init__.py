"""Backend event-stream parsers, registered by name (#514).

Adding a CLI whose events are a NEW shape is one module here and one line in `STREAM_PARSERS`;
a CLI that emits a shape already registered only names that parser. Every reader in the mechanism
goes through `get_stream_parser`, so nothing outside this package knows which shape it is reading.
"""

from __future__ import annotations

from agent_os.streams.claude_jsonl import ClaudeJsonlStreamParser
from agent_os.streams.interface import (
    QuotaStatus,
    ResultUsage,
    StreamParser,
    StreamQuotaVerdict,
    UsageSummary,
)
from agent_os.streams.qwen_jsonl import QwenJsonlStreamParser

STREAM_PARSERS: dict[str, StreamParser] = {
    parser.name: parser for parser in (ClaudeJsonlStreamParser(), QwenJsonlStreamParser())
}

# What a reader that does not know which backend wrote a log parses it with -- a planner run's log,
# the `usage-report` / `cumulative-*` / `quota-status` CLI. Both registered shapes are read the
# same way today, so this is not a guess about the backend.
DEFAULT_STREAM_PARSER = ClaudeJsonlStreamParser.name


class UnknownStreamParserError(ValueError):
    pass


def get_stream_parser(name: str) -> StreamParser:
    try:
        return STREAM_PARSERS[name]
    except KeyError:
        known = ", ".join(sorted(STREAM_PARSERS))
        raise UnknownStreamParserError(
            f"unknown stream parser {name!r} -- registered parsers: {known}"
        ) from None


__all__ = [
    "DEFAULT_STREAM_PARSER",
    "STREAM_PARSERS",
    "QuotaStatus",
    "ResultUsage",
    "StreamParser",
    "StreamQuotaVerdict",
    "UnknownStreamParserError",
    "UsageSummary",
    "get_stream_parser",
]
