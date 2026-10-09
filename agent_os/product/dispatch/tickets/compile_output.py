"""Rendering what `compile` returns: for a person, as JSON, and as files for the issue creator."""

from __future__ import annotations

import json
import pathlib

from agent_os.product.dispatch.tickets.results import CompileResult


def _summary(result: CompileResult) -> dict[str, int]:
    return {
        "tickets": len(result.tickets),
        "escalations": len(result.escalations),
        "goals_skipped": result.goals,
        "containers_skipped": result.containers,
        "past_pending_skipped": result.past_pending,
    }


def render_compile_text(result: CompileResult) -> str:
    summary = _summary(result)
    lines = [
        (
            f"compiled {summary['tickets']} ticket(s), {summary['escalations']} escalation(s); "
            f"not dispatched by this step: {summary['goals_skipped']} goal(s), "
            f"{summary['containers_skipped']} container(s), "
            f"{summary['past_pending_skipped']} node(s) past pending"
        )
    ]
    for ticket in result.tickets:
        lines += [
            "",
            f"=== ticket: {ticket.node_id} ===",
            f"title: {ticket.title}",
            f"labels: {', '.join(ticket.labels)}",
            f"budget: {ticket.budget_class}",
            f"node: {ticket.path}",
            f"depends on: {', '.join(ticket.depends_on) or 'nothing'}",
            f"touches: {', '.join(ticket.touched_paths) or 'no known path'}",
            "---",
            ticket.body.rstrip("\n"),
        ]
    for escalation in result.escalations:
        lines += [
            "",
            f"=== escalation: {escalation.node_id} ===",
            f"{escalation.path}: {escalation.code}: {escalation.message}",
        ]
    return "\n".join(lines) + "\n"


def compile_as_data(result: CompileResult) -> dict:
    return {
        "summary": _summary(result),
        "tickets": [
            {
                "node": ticket.node_id,
                "path": ticket.path,
                "title": ticket.title,
                "labels": list(ticket.labels),
                "budget_class": ticket.budget_class,
                "depends_on": list(ticket.depends_on),
                "touched_paths": list(ticket.touched_paths),
                "body": ticket.body,
            }
            for ticket in result.tickets
        ],
        "escalations": [
            {
                "node": escalation.node_id,
                "path": escalation.path,
                "code": escalation.code,
                "message": escalation.message,
            }
            for escalation in result.escalations
        ],
    }


def render_compile_json(result: CompileResult) -> str:
    return json.dumps(compile_as_data(result), indent=2, ensure_ascii=False) + "\n"


def write_compile_files(result: CompileResult, out_dir: pathlib.Path) -> list[pathlib.Path]:
    """`<node id>.md` per ticket, holding exactly the issue body (what `issues.py create
    --body-file` takes), and `compile.json` holding everything else: titles, labels, escalations."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for ticket in result.tickets:
        path = out_dir / f"{ticket.node_id}.md"
        path.write_text(ticket.body, encoding="utf-8")
        written.append(path)
    index = out_dir / "compile.json"
    index.write_text(render_compile_json(result), encoding="utf-8")
    return [*written, index]
