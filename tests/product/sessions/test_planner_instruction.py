"""The standing instruction for a session reply is in the planner prompt, not only in the issue."""

from __future__ import annotations

from pathlib import Path

from sessions_support import what_question, write_node

from agent_os.product.sessions.batch import build_batch
from agent_os.product.sessions.render import render_session_body
from agent_os.product.tree.loader import load_tree

PLANNER_PROMPT = Path(__file__).resolve().parents[3] / "prompts" / "planner.md"


def test_the_planner_prompt_says_what_to_do_with_a_reply_to_a_question_session():
    prompt = PLANNER_PROMPT.read_text()
    assert "<!-- question-session:v1 -->" in prompt
    assert "agent_os.product.sessions answers" in prompt
    assert "Session-Answer: #<issue>" in prompt


def test_the_session_body_points_at_the_planner_prompt_instead_of_repeating_it(tmp_path):
    write_node(tmp_path, "goal-a", "goal")
    write_node(
        tmp_path,
        "fr-a",
        "functional-requirement",
        parent="goal-a",
        experiments=[what_question("Sort order of notes?", "newest first")],
    )
    body = render_session_body(build_batch(load_tree(tmp_path), []))
    assert "prompts/planner.md" in body
    assert "Session-Answer" not in body
