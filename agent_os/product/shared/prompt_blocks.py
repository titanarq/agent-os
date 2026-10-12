"""Filling a placeholder of a role's prompt template."""

from __future__ import annotations


def substitute_block(text: str, placeholder: str, value: str) -> str:
    """One placeholder, substituted the way the shell drivers substituted it before this function
    existed: inline where it stands inside a line, and as a paragraph of its own where it stands
    alone on one -- an empty value then taking its own line AND the blank line that separated it
    with it, so a host that configures nothing keeps the single blank line every other section
    boundary has instead of a stub heading or a gap twice as wide as the one it fills."""
    if placeholder not in text:
        return text
    block = value.strip("\n")
    lines = text.split("\n")
    rendered: list[str] = []
    for index, line in enumerate(lines):
        if line.strip() == placeholder:
            if block:
                rendered.extend(block.split("\n"))
            elif (
                rendered
                and not rendered[-1].strip()
                and index + 1 < len(lines)
                and not lines[index + 1].strip()
            ):
                # The placeholder was a paragraph between two others: drop one of the two blank
                # lines that fenced it, never both.
                rendered.pop()
            continue
        rendered.append(line.replace(placeholder, block))
    return "\n".join(rendered)
