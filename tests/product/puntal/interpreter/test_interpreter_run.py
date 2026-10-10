"""The interpreter end to end against the fake `claude`: no network, no real backend."""

from __future__ import annotations

import json

from tests.product.puntal.interpreter.interpreter_support import (  # noqa: F401 -- the fixture
    interpret,
    interpreter_environment,
    item,
    model_answer,
    play_answers,
    request_json,
)


def envelope_of(completed) -> dict:
    return json.loads(completed.stdout)


def test_a_message_with_five_things_is_split_into_five_items(tmp_path, environment):
    items = [
        item("change", "Add a label to the checkbox", from_messages=[0]),
        item("change", "Soften the warning"),
        item("decision", "Drop the warning altogether"),
        item("question_of_what", "Should ads expire?"),
        item("change", "Make the box taller"),
    ]
    play_answers(tmp_path, environment, model_answer(reply="I took five things.", items=items))
    completed = interpret(environment, request_json())
    envelope = envelope_of(completed)
    assert completed.returncode == 0, completed.stderr
    assert envelope["outcome"] == "ok" and envelope["needs_answer"] is False
    assert [i["id"] for i in envelope["items"]] == [f"item-{n}" for n in range(1, 6)]
    assert [i["kind"] for i in envelope["items"]] == [
        "change",
        "change",
        "decision",
        "question_of_what",
        "change",
    ]
    assert envelope["message_position"] == 0 and envelope["reply"] == "I took five things."


def test_a_doubt_comes_back_as_one_question_the_host_shows_in_the_chat(tmp_path, environment):
    play_answers(
        tmp_path,
        environment,
        model_answer(reply="Do you want the warning removed, or only quieter?", needs_answer=True),
    )
    envelope = envelope_of(interpret(environment, request_json()))
    assert envelope["needs_answer"] is True and envelope["reply"].endswith("quieter?")
    assert envelope["items"] == []


def test_a_correction_keeps_the_id_and_a_new_item_continues_the_numbering(tmp_path, environment):
    known = {**item(summary="Old reading"), "id": "item-7"}
    play_answers(
        tmp_path,
        environment,
        model_answer(
            items=[
                {**item(summary="New reading", from_messages=[0, 1]), "id": "item-7"},
                item(summary="Another", from_messages=[1]),
            ]
        ),
    )
    thread = [{"role": "owner", "text": "First"}]
    envelope = envelope_of(interpret(environment, request_json(thread=thread, items=[known])))
    assert [(i["id"], i["summary"]) for i in envelope["items"]] == [
        ("item-7", "New reading"),
        ("item-8", "Another"),
    ]
    assert envelope["message_position"] == 1


def test_an_invalid_answer_gets_one_retry_with_the_reasons_and_then_a_clean_error(
    tmp_path, environment
):
    play_answers(tmp_path, environment, "not json at all", model_answer(reply=""))
    completed = interpret(environment, request_json())
    envelope = envelope_of(completed)
    assert completed.returncode == 5 and envelope["outcome"] == "invalid_output"
    assert envelope["reply"] is None and envelope["items"] == [] and envelope["retries"] == 1
    assert "reply" in envelope["detail"]
    assert "Your previous answer was rejected" in (tmp_path / "argv.log").read_text()


def test_a_retry_that_fixes_the_answer_succeeds(tmp_path, environment):
    play_answers(tmp_path, environment, "oops", model_answer(reply="Fixed."))
    envelope = envelope_of(interpret(environment, request_json()))
    assert envelope["outcome"] == "ok" and envelope["retries"] == 1


def test_the_turn_has_no_tool_and_the_telemetry_is_the_puntals_shape(tmp_path, environment):
    play_answers(tmp_path, environment, model_answer(items=[item()]))
    assert interpret(environment, request_json()).returncode == 0
    argv = (tmp_path / "argv.log").read_text()
    assert "--tools=" in argv and "--allowedTools" not in argv
    record = json.loads((tmp_path / "cache" / "telemetry.jsonl").read_text().splitlines()[-1])
    assert record["class"] == "interpreter" and record["action"] == "interpret_feedback"
    assert record["node"] == "uc-publish-an-ad" and record["outcome"] == "ok"
    assert record["labels"]["role"] == "interpreter" and record["cost_usd"] is not None


def test_the_envelope_carries_the_tokens_and_the_latency_the_host_records_in_its_own_line(
    tmp_path, environment
):
    play_answers(tmp_path, environment, model_answer(items=[item()]))
    envelope = envelope_of(interpret(environment, request_json()))
    record = json.loads((tmp_path / "cache" / "telemetry.jsonl").read_text().splitlines()[-1])
    assert envelope["usage"]["total_tokens"] > 0
    assert envelope["usage"] == record["usage"]
    assert envelope["latency_s"] == {"total": record["latency_s"]["total"]}
    assert envelope["latency_s"]["total"] is not None


def test_a_refusal_has_no_usage_and_no_latency_because_nothing_ran(tmp_path, environment):
    envelope = envelope_of(interpret(environment, json.dumps({"message": {"text": ""}})))
    assert envelope["outcome"] == "not_run"
    assert envelope["usage"] is None and envelope["latency_s"] is None


def test_a_model_that_fails_leaves_a_not_ok_envelope_for_the_host_to_note(tmp_path, environment):
    environment["FAKE_PUNTAL_FAULT"] = "crash"
    completed = interpret(environment, request_json())
    envelope = envelope_of(completed)
    assert completed.returncode == 1 and envelope["outcome"] == "error"
    assert envelope["reply"] is None and envelope["detail"]


def test_a_bad_request_is_refused_before_anything_is_spent(tmp_path, environment):
    completed = interpret(environment, json.dumps({"message": {"role": "agent", "text": "x"}}))
    envelope = envelope_of(completed)
    assert completed.returncode == 2 and envelope["outcome"] == "not_run"
    assert not (tmp_path / "argv.log").exists()


def test_a_case_missing_from_the_tree_is_refused(tmp_path, environment):
    tree = tmp_path / "tree"
    tree.mkdir()
    completed = interpret(environment, request_json(case=None), "--tree-root", str(tree))
    assert (
        completed.returncode == 2 and "not a node of the tree" in envelope_of(completed)["detail"]
    )


def test_the_case_is_read_from_the_tree_when_the_request_carries_only_its_id(tmp_path, environment):
    environment["AGENTS_CONFIG_PATH"] = str(tmp_path / "unused")  # replaced below
    from agent_os.cli import AGENT_OS_DIR

    environment["AGENTS_CONFIG_PATH"] = str(AGENT_OS_DIR / "config.example.yaml")
    tree = AGENT_OS_DIR / "docs" / "tree"
    case_id = "uc-open-a-test-session-for-a-branch"
    message = {"text": "The button is hidden.", "case": case_id}
    completed = interpret(
        environment, request_json(case=None, message=message), "--tree-root", str(tree), "--dry-run"
    )
    assert completed.returncode == 0, completed.stderr
    assert f"id: {case_id}" in completed.stdout and "# Case" in completed.stdout
