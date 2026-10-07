"""The batch of a session: which questions, in what order, and what the issue body says."""

from __future__ import annotations

from sessions_support import what_question, write_node

from agent_os.product.sessions.batch import build_batch
from agent_os.product.sessions.render import read_frozen_batch, render_session_body
from agent_os.product.tree.loader import load_tree


def build_tree(tmp_path):
    write_node(tmp_path, "goal-a", "goal")
    write_node(tmp_path, "goal-b", "goal")
    write_node(
        tmp_path,
        "fr-a",
        "functional-requirement",
        parent="goal-a",
        experiments=[what_question("Sort order of notes?", "newest first")],
    )
    write_node(tmp_path, "uc-a1", "use-case", parent="fr-a")
    write_node(tmp_path, "uc-a2", "use-case", parent="fr-a", depends_on=["fr-a"])
    write_node(
        tmp_path,
        "fr-b",
        "functional-requirement",
        parent="goal-b",
        experiments=[
            what_question("Who may share?", "only the author"),
            {
                "kind": "question",
                "question": "A how doubt",
                "outcome": "open",
                "date": "2026-10-01",
                "scope": "how",
            },
            what_question("Already answered", "x", outcome="answered", finding="y"),
        ],
        challenge={"reason": "over-cost", "explanation": "too dear"},
    )
    return load_tree(tmp_path)


def test_only_open_what_questions_are_numbered_and_the_one_blocking_more_comes_first(tmp_path):
    batch = build_batch(build_tree(tmp_path), [])
    assert [(q.number, q.node_id) for q in batch.questions] == [(1, "fr-a"), (2, "fr-b")]
    assert batch.questions[0].blocks == 2 and batch.questions[0].branch_id == "goal-a"
    assert batch.questions[1].blocks == 0


def test_the_body_groups_by_branch_and_shows_each_default_and_the_challenges(tmp_path):
    body = render_session_body(build_batch(build_tree(tmp_path), []))
    assert body.index("Branch `goal-a`") < body.index("**1.**") < body.index("Branch `goal-b`")
    assert "default, which stands until you answer: newest first" in body
    assert "`fr-b` -- over-cost: too dear" in body
    assert "1: yes; 3: no, rather" in body


def test_the_digest_lists_judgments_and_the_frozen_block_round_trips(tmp_path):
    judgment = {
        "judgment_id": "j-1",
        "role": "refiner",
        "kind": "soft",
        "node": "fr-a",
        "decision": "Use weekly view.",
    }
    batch = build_batch(build_tree(tmp_path), [judgment])
    body = render_session_body(batch)
    assert "Decided without you" in body and "Use weekly view." in body
    frozen = read_frozen_batch(body)
    assert frozen["questions"][0]["default_answer"] == "newest first"
    assert frozen["digest"] == [
        {"number": 1, "judgment_id": "j-1", "node": "fr-a", "decision": "Use weekly view."}
    ]


def test_a_long_digest_is_cut_to_the_latest_entries_and_says_how_many_it_left_out(tmp_path):
    judgments = [
        {"judgment_id": f"j-{i}", "role": "r", "kind": "k", "node": None, "decision": f"d{i}"}
        for i in range(25)
    ]
    batch = build_batch(build_tree(tmp_path), judgments)
    assert len(batch.digest) == 20 and batch.digest_omitted == 5
    assert batch.digest[-1].decision == "d24"


def test_nothing_waiting_is_an_empty_batch(tmp_path):
    write_node(tmp_path, "goal-a", "goal")
    assert build_batch(load_tree(tmp_path), []).is_empty
