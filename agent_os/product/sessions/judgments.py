"""The judgments log: what an agent decided alone, and what later came of it.

`docs/AGENTOS_V2_PLAN.md` ("Recording conventions"): two append-only JSON-lines files under the
host's `.cache/judgments/`, joined by `judgment_id`.

`judgments.jsonl`, one line per judgment:

    {"schema": 1, "judgment_id": "...", "recorded_at": "<UTC ISO-8601>",
     "role": "refiner", "kind": "soft-product-decision", "node": "<node id> | null",
     "decision": "what was decided, in one sentence", "scope": "what | how",
     "versions": {"model": ..., "cli_version": ..., "method_version": {...}}}

`outcomes.jsonl`, one line per later finding about a judgment (a judgment may have several):

    {"schema": 1, "judgment_id": "...", "recorded_at": "...",
     "outcome": "confirmed | reversed | reclaimed", "source": "who or what found it",
     "detail": "one sentence" | null}

`scope` says whose call it was: a `how` judgment is the agents' to take; a `what` one was taken
only because the owner was not asked, and is what a question session's digest puts back in front
of the owner. `versions` is `agent_os.product.records.record_versions`: without it a change in how
often judgments are reversed cannot be told from a change of model or of prompt.
"""

from __future__ import annotations

import datetime
import pathlib
import uuid

from agent_os.product.records import append_json_line, read_json_lines

SCHEMA_VERSION = 1
JUDGMENTS_FILE = "judgments.jsonl"
OUTCOMES_FILE = "outcomes.jsonl"
SCOPES = ("what", "how")
OUTCOMES = ("confirmed", "reversed", "reclaimed")


class JudgmentError(ValueError):
    """A record that does not fit the schema, or an outcome for a judgment nobody recorded."""


def judgments_directory(cache_directory: pathlib.Path) -> pathlib.Path:
    return cache_directory / "judgments"


def _now() -> str:
    return datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_timestamp(text: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(text)


def _require_text(name: str, value: str | None) -> str:
    if value is None or not value.strip() or "\n" in value.strip():
        raise JudgmentError(f"`{name}` must be one non-blank line")
    return value.strip()


def record_judgment(
    cache_directory: pathlib.Path,
    *,
    role: str,
    kind: str,
    node: str | None,
    decision: str,
    scope: str,
    versions: dict,
    recorded_at: str | None = None,
) -> str:
    """Appends one judgment and returns its id."""
    if scope not in SCOPES:
        raise JudgmentError(f"`scope` must be one of {', '.join(SCOPES)}, not {scope!r}")
    judgment_id = f"j-{uuid.uuid4().hex[:12]}"
    append_json_line(
        judgments_directory(cache_directory) / JUDGMENTS_FILE,
        {
            "schema": SCHEMA_VERSION,
            "judgment_id": judgment_id,
            "recorded_at": recorded_at or _now(),
            "role": _require_text("role", role),
            "kind": _require_text("kind", kind),
            "node": node.strip() if node and node.strip() else None,
            "decision": _require_text("decision", decision),
            "scope": scope,
            "versions": versions,
        },
    )
    return judgment_id


def read_judgments(cache_directory: pathlib.Path) -> list[dict]:
    return read_json_lines(judgments_directory(cache_directory) / JUDGMENTS_FILE)


def find_judgment(cache_directory: pathlib.Path, judgment_id: str) -> dict:
    for judgment in read_judgments(cache_directory):
        if judgment.get("judgment_id") == judgment_id:
            return judgment
    raise JudgmentError(f"no judgment {judgment_id!r} in the log")


def record_outcome(
    cache_directory: pathlib.Path,
    *,
    judgment_id: str,
    outcome: str,
    source: str,
    detail: str | None = None,
    recorded_at: str | None = None,
) -> None:
    """Appends the later finding about a judgment. An unknown judgment is an error: an outcome that
    points at nothing would be counted against no one."""
    if outcome not in OUTCOMES:
        raise JudgmentError(f"`outcome` must be one of {', '.join(OUTCOMES)}, not {outcome!r}")
    find_judgment(cache_directory, judgment_id)
    append_json_line(
        judgments_directory(cache_directory) / OUTCOMES_FILE,
        {
            "schema": SCHEMA_VERSION,
            "judgment_id": judgment_id,
            "recorded_at": recorded_at or _now(),
            "outcome": outcome,
            "source": _require_text("source", source),
            "detail": detail.strip() if detail and detail.strip() else None,
        },
    )


def read_outcomes(cache_directory: pathlib.Path) -> list[dict]:
    return read_json_lines(judgments_directory(cache_directory) / OUTCOMES_FILE)


def judgments_since(cache_directory: pathlib.Path, moment: str | None) -> list[dict]:
    """Judgments recorded after `moment` (all of them when there is no earlier moment)."""
    judgments = read_judgments(cache_directory)
    if moment is None:
        return judgments
    limit = parse_timestamp(moment)
    return [j for j in judgments if parse_timestamp(j["recorded_at"]) > limit]
