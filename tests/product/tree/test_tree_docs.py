"""The docs agree with the code they describe: the checks, the schema fields, the config keys, the ADR.

Expected values come from the code itself -- the doctor's own list of checks, the models' own
fields, the example config -- never from a list copied into this file, so adding a check, a field
or a key without documenting it fails here instead of going unnoticed.

Pure filesystem. No backend, no network.
"""

from __future__ import annotations

import importlib
import re
import tomllib

import pytest

from agent_os.cli import AGENT_OS_DIR
from agent_os.lib import TreeConfig
from agent_os.product.tree.checks import CHECKS
from agent_os.product.tree.compile import MECHANISM_UNRESOLVABLE
from agent_os.product.tree.models import (
    Challenge,
    Decision,
    Experiment,
    FrictionEntry,
    Node,
    RejectedAlternative,
    Verification,
)

AGENT_OS_DOC = AGENT_OS_DIR / "docs" / "AGENT_OS.md"
ADR = (
    AGENT_OS_DIR
    / "docs"
    / "adr"
    / "2026-10-04-the-product-tree-and-the-decision-ledger-are-markdown-files-with-a-doctor.md"
)


def section_of_the_tree_doc() -> str:
    text = AGENT_OS_DOC.read_text()
    start = text.index("### 4.6 The product tree and the decision ledger")
    # Up to the next heading of any level that is a section: a subsection that follows (the puntal
    # driver's, 4.7) is another feature's text and must not satisfy this one's documentation.
    following = re.search(r"\n#{2,3} ", text[start + 1 :])
    assert following, "the tree section is the last in the document, so where does it end?"
    return text[start : start + 1 + following.start()]


def test_the_docs_table_lists_every_check_the_doctor_has():
    section = section_of_the_tree_doc()
    documented = set(re.findall(r"^\| `([a-z-]+)` \|", section, flags=re.MULTILINE))
    assert documented >= set(CHECKS), sorted(set(CHECKS) - documented)


def test_the_docs_table_lists_no_check_the_doctor_lacks():
    section = section_of_the_tree_doc()
    after_the_doctor = section.split("**The doctor**")[1].split("**The slice**")[0]
    documented = set(re.findall(r"^\| `([a-z-]+)` \|", after_the_doctor, flags=re.MULTILINE))
    assert documented == set(CHECKS)


def test_the_docs_name_the_escalation_code():
    section = section_of_the_tree_doc()
    assert f"`{MECHANISM_UNRESOLVABLE}`" in section


@pytest.mark.parametrize(
    "model",
    [Node, Verification, Decision, Experiment, Challenge, RejectedAlternative, FrictionEntry],
)
def test_the_docs_name_every_field_of_every_schema(model):
    section = section_of_the_tree_doc()
    # A node's description and a decision's statement are the Markdown body, documented as such.
    undocumented = [
        name
        for name in model.model_fields
        if f"`{name}`" not in section and name not in ("description", "statement")
    ]
    assert not undocumented, f"{model.__name__}: {undocumented}"
    assert "the `description`" in section and "the `statement`" in section


def test_the_docs_name_the_config_keys():
    text = AGENT_OS_DOC.read_text()
    for key in TreeConfig.model_fields:
        assert f"`tree.{key}`" in text


def test_the_adr_exists_and_the_index_lists_it():
    assert ADR.is_file()
    index = (AGENT_OS_DIR / "docs" / "adr" / "README.md").read_text()
    assert f"[`{ADR.name}`](./{ADR.name})" in index


def test_the_changelog_and_the_docs_point_at_the_adr_by_its_real_name():
    for path in (AGENT_OS_DIR / "docs" / "CHANGELOG.md", AGENT_OS_DOC):
        assert ADR.name in path.read_text(), path


def test_the_adr_dates_the_change_to_a_judged_verification_and_the_changelog_names_it():
    adr = ADR.read_text()
    assert (
        "Changed 2026-10-06: a verification is a command or a judged criterion; "
        "a goal without evaluators is a red check" in adr
    )
    for decision in (
        "dec-top-down-acceptance-is-essential-even-when-judged",
        "dec-a-goal-without-evaluators-is-a-red-check",
        "dec-tests-harden-they-do-not-build",
    ):
        assert f"docs/tree/{decision}.md" in adr
    changelog = (AGENT_OS_DIR / "docs" / "CHANGELOG.md").read_text()
    unreleased = changelog.split("## Unreleased")[1].split("\n- ", 2)[1]
    assert "goal-without-evaluators" in unreleased and "`judge`" in unreleased


def test_the_docs_say_what_a_hardened_node_needs_and_that_a_goal_needs_evaluators():
    section = section_of_the_tree_doc()
    hardened = re.search(r"^\| `hardened-needs-verification` \| (.+) \|$", section, re.MULTILINE)
    assert hardened and "`command`" in hardened.group(1)
    goal = re.search(r"^\| `goal-without-evaluators` \| (.+) \|$", section, re.MULTILINE)
    assert goal and "`verification`" in goal.group(1)


def test_the_console_script_resolves_to_a_callable():
    scripts = tomllib.loads((AGENT_OS_DIR / "pyproject.toml").read_text())["project"]["scripts"]
    module_name, _, attribute = scripts["agent-os-tree"].partition(":")
    assert callable(getattr(importlib.import_module(module_name), attribute))
