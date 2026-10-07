"""Which pull requests touch the owner's what, and which transcribe a session answer exactly."""

from __future__ import annotations

import pathlib

from sessions_support import what_question, write_node

from agent_os.product.sessions.reply import resolve_reply
from agent_os.product.sessions.transcription import verify_transcription
from agent_os.product.sessions.what_guard import BASE, HEAD, FileChange, find_what_touches
from agent_os.product.sessions.writeback import answer_question
from agent_os.product.tree.loader import load_tree

QUESTION = "Sort order?"
FROZEN = {
    "questions": [{"number": 1, "node": "fr-a", "question": QUESTION, "default_answer": "newest"}],
    "digest": [{"number": 1, "judgment_id": "j-1", "node": "fr-a", "decision": "weekly view"}],
}


def reader(files: dict[tuple[str, str], str]):
    return lambda side, path: files.get((side, path))


def text_of(path: pathlib.Path) -> str:
    return path.read_text()


def touches(changes, files, owner_only=()):
    return find_what_touches(
        changes, tree_root="product", owner_only_paths=list(owner_only), read_file=reader(files)
    )


def test_a_goal_node_is_the_what_and_a_use_case_is_not(tmp_path):
    goal = text_of(write_node(tmp_path, "goal-a", "goal"))
    use_case = text_of(write_node(tmp_path, "uc-a", "use-case", parent="fr-a"))
    files = {
        (HEAD, "product/goal-a.md"): goal,
        (BASE, "product/goal-a.md"): goal,
        (HEAD, "product/uc-a.md"): use_case,
        (BASE, "product/uc-a.md"): use_case,
    }
    assert [t.path for t in touches([FileChange("product/goal-a.md")], files)] == [
        "product/goal-a.md"
    ]
    assert touches([FileChange("product/uc-a.md"), FileChange("src/app.py")], files) == []


def test_a_goal_deleted_or_renamed_away_still_counts(tmp_path):
    goal = text_of(write_node(tmp_path, "goal-a", "goal"))
    deleted = touches([FileChange("product/goal-a.md")], {(BASE, "product/goal-a.md"): goal})
    renamed = touches(
        [FileChange("product/elsewhere/goal-a.md", "product/goal-a.md")],
        {(BASE, "product/goal-a.md"): goal, (HEAD, "product/elsewhere/goal-a.md"): goal},
    )
    assert deleted and renamed


def test_an_unreadable_file_under_the_tree_root_counts_as_the_what():
    found = touches(
        [FileChange("product/broken.md")], {(HEAD, "product/broken.md"): "no frontmatter"}
    )
    assert found and "cannot be read" in found[0].reason


def test_a_host_listed_evaluator_path_is_the_what():
    found = touches([FileChange("eval/thresholds.yaml")], {}, owner_only=["eval/*.yaml"])
    assert [t.path for t in found] == ["eval/thresholds.yaml"]


def answered_pair(tmp_path, answer="oldest"):
    write_node(tmp_path / "base", "goal-a", "goal")
    write_node(
        tmp_path / "base",
        "fr-a",
        "functional-requirement",
        parent="goal-a",
        experiments=[what_question(QUESTION, "newest")],
    )
    tree = load_tree(tmp_path / "base")
    before = text_of(tree.paths["fr-a"])
    answer_question(tree, "fr-a", QUESTION, answer)
    return before, text_of(tree.paths["fr-a"])


def verify(before, after, reply_text="1: no, rather oldest", extra=()):
    files = {(BASE, "product/fr-a.md"): before, (HEAD, "product/fr-a.md"): after}
    return verify_transcription(
        [FileChange("product/fr-a.md"), *extra],
        tree_root="product",
        read_file=reader(files),
        reply=resolve_reply([reply_text], FROZEN),
    )


def test_a_pull_request_that_writes_the_answer_word_for_word_is_a_transcription(tmp_path):
    before, after = answered_pair(tmp_path)
    assert verify(before, after) == []


def test_an_accepted_default_is_transcribed_as_the_default(tmp_path):
    before, after = answered_pair(tmp_path, answer="newest")
    assert verify(before, after, "1: yes") == []


def test_a_different_wording_is_not_a_transcription(tmp_path):
    before, after = answered_pair(tmp_path, answer="oldest first, please")
    assert "experiment 1 is changed but is not an answer" in verify(before, after)[0]


def test_an_answer_the_owner_did_not_give_is_not_a_transcription(tmp_path):
    before, after = answered_pair(tmp_path)
    assert verify(before, after, "1: no, rather by title")


def test_any_other_change_to_the_node_breaks_the_transcription(tmp_path):
    before, after = answered_pair(tmp_path)
    assert verify(before, after.replace("Title of fr-a", "A new title"))
    assert verify(before, after + "one more line\n")


def test_a_file_other_than_the_node_breaks_the_transcription(tmp_path):
    before, after = answered_pair(tmp_path)
    assert verify(before, after, extra=[FileChange("src/app.py")])


def test_a_reclaimed_decision_added_as_a_question_is_a_transcription(tmp_path):
    write_node(tmp_path / "base", "goal-a", "goal")
    write_node(tmp_path / "base", "fr-a", "functional-requirement", parent="goal-a")
    tree = load_tree(tmp_path / "base")
    before = text_of(tree.paths["fr-a"])
    import datetime

    from agent_os.product.sessions.writeback import raise_reclaimed_question

    raise_reclaimed_question(tree, "fr-a", "weekly view", raised_on=datetime.date(2026, 10, 7))
    after = text_of(tree.paths["fr-a"])
    assert verify(before, after, "reclaim 1") == []
    assert verify(before, after, "1: yes")
