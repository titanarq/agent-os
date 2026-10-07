"""What the puntal is told about THIS click."""

from __future__ import annotations

import json


def build_brief(
    *,
    node_slice: str,
    action: str,
    payload: str,
    relevant_state: str,
    loaded_state: str | None = None,
    extra_sections: tuple[tuple[str, str], ...] = (),
) -> str:
    """The node slice (it carries its own title), then the action, its payload, the state the app
    passed in, the state the pre-helper loaded (when the node declares any) and, last, the sections a
    retry or the slow path adds. Assembled here, not rendered from a template: the payload is a
    person's text, and running it through placeholder substitution would let a payload that contains
    `__NODE__` rewrite the brief."""
    node_text = node_slice.strip()
    if node_text.startswith("-"):
        # The brief is the CLI's positional argument: text that opens with a dash is read as an option.
        node_text = f"# Node\n\n{node_text}"
    parts = [
        node_text,
        f"# Action\n\n{action}",
        f"# Payload\n\n{payload.strip() or '(none)'}",
        f"# State passed in by the app\n\n{relevant_state.strip() or '(none)'}",
    ]
    if loaded_state is not None:
        parts.append(
            "# State loaded for this action\n\n"
            "Read from the persisted state by code, just before you were run: this is the truth.\n\n"
            f"{loaded_state.strip() or '(the node declares nothing to read)'}"
        )
    parts += [f"# {heading}\n\n{body.strip()}" for heading, body in extra_sections]
    return "\n\n".join(parts) + "\n"


def rejected_plan_section(response_text: str, errors: list[str]) -> tuple[str, str]:
    """The retry turn's one extra section: what was sent, and why it was not applied."""
    listed = "\n".join(f"- {error}" for error in errors)
    return (
        "Your previous plan was rejected",
        (
            f"You sent:\n\n{response_text.strip()}\n\n"
            f"It was NOT applied (nothing changed), because:\n\n{listed}\n\n"
            "Send the corrected plan, in the same form."
        ),
    )


def slow_path_section(reason: str) -> tuple[str, str]:
    """The slow path's: why this turn has the persistence tool the fast one did not."""
    return (
        "Why you have a tool this time",
        (
            f"Your first turn said it needed state the node does not declare: {reason}\n\n"
            "Read it through the persistence tool, do what the node says through it, and answer."
        ),
    )


def previous_attempt_section(attempt: dict) -> tuple[str, str]:
    """A rejected plan the APP is handing back (it applied plans itself and one failed)."""
    errors = [str(error) for error in attempt.get("errors") or []]
    return rejected_plan_section(json.dumps(attempt.get("plan"), ensure_ascii=False), errors)
