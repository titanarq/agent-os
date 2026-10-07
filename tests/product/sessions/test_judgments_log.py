"""The judgments log: one line per judgment, one per outcome, stamped with the versions."""

from __future__ import annotations

import json

import pytest

from agent_os.product.sessions import judgments

VERSIONS = {"model": "m", "cli_version": "1", "method_version": {"agent_os_commit": None}}


def record(tmp_path, **overrides):
    fields = {
        "role": "refiner",
        "kind": "soft-product-decision",
        "node": "uc-edit",
        "decision": "Notes sort newest first.",
        "scope": "what",
        "versions": VERSIONS,
    }
    fields.update(overrides)
    return judgments.record_judgment(tmp_path, **fields)


def test_a_judgment_is_one_json_line_with_its_schema(tmp_path):
    judgment_id = record(tmp_path)
    lines = (tmp_path / "judgments" / "judgments.jsonl").read_text().splitlines()
    assert len(lines) == 1
    written = json.loads(lines[0])
    assert written["judgment_id"] == judgment_id
    assert written["schema"] == 1
    assert written["versions"] == VERSIONS
    assert {"recorded_at", "role", "kind", "node", "decision", "scope"} <= written.keys()


def test_a_scope_outside_what_and_how_is_refused_and_writes_nothing(tmp_path):
    with pytest.raises(judgments.JudgmentError, match="scope"):
        record(tmp_path, scope="maybe")
    assert judgments.read_judgments(tmp_path) == []


def test_a_decision_over_several_lines_is_refused(tmp_path):
    with pytest.raises(judgments.JudgmentError, match="decision"):
        record(tmp_path, decision="one\ntwo")


def test_an_outcome_is_joined_to_its_judgment_by_id(tmp_path):
    judgment_id = record(tmp_path)
    judgments.record_outcome(tmp_path, judgment_id=judgment_id, outcome="reversed", source="pr #9")
    judgments.record_outcome(
        tmp_path, judgment_id=judgment_id, outcome="reclaimed", source="session", detail="mine"
    )
    outcomes = judgments.read_outcomes(tmp_path)
    assert [o["outcome"] for o in outcomes] == ["reversed", "reclaimed"]
    assert {o["judgment_id"] for o in outcomes} == {judgment_id}


def test_an_outcome_for_an_unknown_judgment_is_an_error(tmp_path):
    with pytest.raises(judgments.JudgmentError, match="no judgment"):
        judgments.record_outcome(tmp_path, judgment_id="j-nope", outcome="confirmed", source="x")


def test_judgments_since_keeps_only_the_later_ones(tmp_path):
    record(tmp_path, recorded_at="2026-10-01T10:00:00Z", decision="old")
    record(tmp_path, recorded_at="2026-10-03T10:00:00Z", decision="new")
    later = judgments.judgments_since(tmp_path, "2026-10-02T00:00:00Z")
    assert [j["decision"] for j in later] == ["new"]
    assert len(judgments.judgments_since(tmp_path, None)) == 2
