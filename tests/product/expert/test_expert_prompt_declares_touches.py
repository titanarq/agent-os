"""The expert declares the code each node touches, because dispatch can only keep two tickets off
the same code when it is told what the code is.

On the first v2 host two tickets depended on the same code without either node saying so: with no
`touches:` the paths are guessed from prose, and a node that names no path collides with nothing,
so both ran at once. When work that could be parallel is not, the brake is the granularity of the
tree (`fr-independent-work-runs-in-parallel`): the expert is who sets it, node by node.
"""

from __future__ import annotations

from agent_os.cli import AGENT_OS_DIR

EXPERT_PROMPT = AGENT_OS_DIR / "prompts" / "expert.md"


def prompt_words() -> str:
    return " ".join(EXPERT_PROMPT.read_text().split())


def test_the_expert_is_told_to_declare_touches_on_every_node_that_becomes_a_ticket():
    prompt = prompt_words()
    assert "`touches:`" in prompt
    assert "node that compiles to a ticket (a pending leaf) carries `touches:`" in prompt


def test_the_expert_is_told_a_node_that_names_no_path_collides_with_nothing():
    prompt = prompt_words()
    assert "a node that names no path collides with nothing" in prompt


def test_the_expert_splits_a_node_instead_of_letting_two_independent_ones_share_code():
    prompt = prompt_words()
    assert "two independent nodes would touch the same code, split" in prompt
    assert "`depends_on:`" in prompt


def test_the_expert_never_narrows_touches_to_hide_a_collision():
    assert "never a narrower path than the node will really change" in prompt_words()
