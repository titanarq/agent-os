"""What a puntal's tool call may be: the audit of one call, and the gap note a final message carries."""

from __future__ import annotations

import shlex

from agent_os.product.puntal.constants import GAP_MARKER, PERSISTENCE_TOOL, STATE_COMMAND

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
