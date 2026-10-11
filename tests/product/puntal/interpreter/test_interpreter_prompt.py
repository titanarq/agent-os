"""The interpreter's prompt: what it renders to, and that nothing host-specific leaks into it."""

from __future__ import annotations

import re

from agent_os.cli import AGENT_OS_DIR
from agent_os.lib import PROJECT_EXTRAS_PLACEHOLDER, render_prompt
from agent_os.product.interpreter.options import PROPOSAL_RULES_PATH, REVIEW_MODE_RULES_PATH

TEMPLATE = AGENT_OS_DIR / "prompts" / "interpreter.md"
GOLDEN = AGENT_OS_DIR / "tests" / "golden" / "interpreter.md"


def _words(text: str) -> list[str]:
    return text.split()


def _render(language: str, *, review_mode: bool = False) -> str:
    """As `resolve_options` renders it: the proposal rules always, review mode when it is on."""
    return render_prompt(
        "interpreter",
        {
            "REVIEW_MODE_RULES": REVIEW_MODE_RULES_PATH.read_text() if review_mode else "",
            "PROPOSAL_RULES": PROPOSAL_RULES_PATH.read_text(),
            "REPLY_LANGUAGE": language,
        },
    )


def test_the_prompt_renders_exactly_the_golden_in_the_owners_language():
    rendered = _render("the language the owner's latest message is written in")
    assert _words(rendered) == _words(GOLDEN.read_text())


def test_a_configured_language_replaces_the_owners_in_the_reply_rule():
    assert "Write it in Spanish." in _render("Spanish")


def test_review_mode_adds_its_paragraph_and_nothing_else_changes():
    assert "REVIEW MODE IS ON" not in _render("Spanish")
    assert "REVIEW MODE IS ON" in _render("Spanish", review_mode=True)


def test_the_template_carries_the_hosts_extension_point_and_names_no_host_script():
    text = TEMPLATE.read_text()
    assert PROJECT_EXTRAS_PLACEHOLDER in text
    assert not re.findall(r"(?<![\w./-])scripts/[\w./-]+", text)


def test_the_prompt_tells_the_three_kinds_apart_and_the_three_origins():
    text = TEMPLATE.read_text()
    for word in (
        "`change`",
        "`decision`",
        "`question_of_what`",
        "`stated`",
        "`derived`",
        "`detected`",
    ):
        assert word in text
    assert "the owner's word on the what" in text
