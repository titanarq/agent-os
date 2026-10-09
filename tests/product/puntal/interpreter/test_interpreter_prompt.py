"""The interpreter's prompt: what it renders to, and that nothing host-specific leaks into it."""

from __future__ import annotations

import re

from agent_os.cli import AGENT_OS_DIR
from agent_os.lib import PROJECT_EXTRAS_PLACEHOLDER, render_prompt

TEMPLATE = AGENT_OS_DIR / "prompts" / "interpreter.md"
GOLDEN = AGENT_OS_DIR / "tests" / "golden" / "interpreter.md"


def _words(text: str) -> list[str]:
    return text.split()


def test_the_prompt_renders_exactly_the_golden_in_the_owners_language():
    rendered = render_prompt(
        "interpreter", {"REPLY_LANGUAGE": "the language the owner's latest message is written in"}
    )
    assert _words(rendered) == _words(GOLDEN.read_text())


def test_a_configured_language_replaces_the_owners_in_the_reply_rule():
    rendered = render_prompt("interpreter", {"REPLY_LANGUAGE": "Spanish"})
    assert "Write it in Spanish." in rendered


def test_the_template_carries_the_hosts_extension_point_and_names_no_host_script():
    text = TEMPLATE.read_text()
    assert PROJECT_EXTRAS_PLACEHOLDER in text
    assert not re.findall(r"(?<![\w./-])scripts/[\w./-]+", text)


def test_the_prompt_tells_the_three_kinds_apart_and_that_the_owner_decides_the_what():
    text = TEMPLATE.read_text()
    for kind in ("`change`", "`decision`", "`question_of_what`"):
        assert kind in text
    assert "The owner decides those" in text
