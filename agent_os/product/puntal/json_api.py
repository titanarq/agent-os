"""The generic API for a host's shell: JSON in, JSON out, independent of the app's stack.

    puntal_task.sh --json [--plan-only]      reads ONE request object on stdin, prints ONE envelope

The request (a shell in any language builds it): `action` (required), `node` -- the node slice as
text, which may open with the frontmatter that declares its `reads` -- or `node_file`, `node_id`,
`payload` (any JSON value; text stays text), `state` (text, or any JSON value), `reads` (more read
commands, as a node declares them), `session_id`, `invocation_id`, `labels` (an object),
`retry_of` (an invocation id: a retry the owner asked for), `previous_attempt`
(`{"plan": ..., "errors": [...]}`: a plan the app applied itself and could not) and `actor` (who
clicked: text, set as `PUNTAL_ACTOR` for the app's own commands -- the reads, the executor, the slow
path's tool -- see `fast/actor.py`).

The envelope: `invocation_id`, `outcome` (the telemetry's: `ok`, `error`, `timeout`,
`contract_violation`, `ceiling_cut`, `invalid_plan`, `executor_failed`, or `not_run`), `exit_status`,
`detail`, `path` (`fast` or `slow`), `answer` (a JSON value, or text), `answer_text` (what the plain
CLI would print), `operations` (the validated plan's), `bindings`, `applied`, `gap_note`, `retries`.
With `--plan-only` nothing is applied: `operations` and `answer` come back as the puntal wrote them,
`{{name}}` placeholders and all, for the app to apply through its own API and fill in.
"""

from __future__ import annotations

import json
import uuid

from agent_os.product.puntal.constants import EXIT_NOT_RUN, PuntalRefused
from agent_os.product.puntal.fast.operations import fill_bindings
from agent_os.product.puntal.fast.pre_helper import split_node_declaration
from agent_os.product.puntal.options import Request, read_text


def _text_of(value: object) -> str:
    if value is None:
        return ""
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def request_from_json(text: str) -> Request:
    try:
        document = json.loads(text)
    except ValueError as error:
        raise PuntalRefused(f"the request is not JSON ({error})") from error
    if not isinstance(document, dict):
        raise PuntalRefused("the request must be one JSON object")
    action = document.get("action")
    if not isinstance(action, str) or not action:
        raise PuntalRefused("the request needs an `action`")
    node_text = document.get("node")
    if node_text is None and document.get("node_file"):
        node_text = read_text(document["node_file"], what="the node file")
    if not isinstance(node_text, str) or not node_text.strip():
        raise PuntalRefused("the request needs a `node` (the slice as text) or a `node_file`")
    node_id = document.get("node_id")
    if not node_id and document.get("node_file"):
        node_id = str(document["node_file"]).rsplit("/", 1)[-1].removesuffix(".md")
    if not node_id:
        raise PuntalRefused("the request needs a `node_id` when it carries the node as text")
    labels = document.get("labels") or {}
    if not isinstance(labels, dict):
        raise PuntalRefused("`labels` must be an object")
    labels = {str(key): str(value) for key, value in labels.items()}
    if document.get("retry_of"):
        labels["retry_of"] = str(document["retry_of"])
    reads = document.get("reads") or []
    if not isinstance(reads, list) or not all(isinstance(read, str) for read in reads):
        raise PuntalRefused("`reads` must be a list of read commands (strings)")
    attempt = document.get("previous_attempt")
    if attempt is not None and not isinstance(attempt, dict):
        raise PuntalRefused("`previous_attempt` must be an object")
    actor = document.get("actor", "")
    if not isinstance(actor, str) or "\x00" in actor:
        raise PuntalRefused("`actor` must be text: who clicked, for the app's own commands")
    declaration = split_node_declaration(node_text)
    return Request(
        action=action,
        node_id=str(node_id),
        node_slice=declaration.slice_text,
        payload=_text_of(document.get("payload")),
        relevant_state=_text_of(document.get("state")),
        session_id=str(document.get("session_id") or ""),
        invocation_id=str(document.get("invocation_id") or uuid.uuid4()),
        labels=labels,
        declared_reads=[*declaration.reads, *(read.strip() for read in reads)],
        declaration_problems=declaration.problems,
        previous_attempt=attempt,
        actor=actor.strip(),
    )


def envelope(request: Request, result, *, plan_only: bool) -> dict:
    """The response document for a finished invocation (`InvocationResult`)."""
    trace = result.trace
    plan = result.plan
    if plan is None:
        answer: object = result.answer or None
    elif plan_only or not result.applied:
        answer = plan.answer
    else:
        answer = fill_bindings(plan.answer, result.bindings)
    return {
        "invocation_id": request.invocation_id,
        "outcome": trace.outcome,
        "exit_status": result.status,
        "detail": trace.outcome_detail,
        "path": trace.path,
        "answer": answer,
        "answer_text": result.answer,
        "operations": plan.operations if plan is not None and not plan.asks_for_state else [],
        "bindings": result.bindings,
        "applied": result.applied,
        "gap_note": trace.gap_note,
        "retries": trace.plan["retries"],
    }


def refusal_envelope(refusal: PuntalRefused, invocation_id: str | None = None) -> dict:
    return {
        "invocation_id": invocation_id,
        "outcome": "not_run",
        "exit_status": EXIT_NOT_RUN,
        "detail": str(refusal),
        "path": None,
        "answer": None,
        "answer_text": "",
        "operations": [],
        "bindings": {},
        "applied": False,
        "gap_note": None,
        "retries": 0,
    }
