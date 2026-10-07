"""The bench measuring the FAST path: the same helpdesk, the same oracles, a puntal that plans in one
turn and an executor (`bench/puntal/executor.py`) that applies it. Dry runs only, against the fake.

Pure filesystem and subprocess. This file must not request the `engine` or `db_sandbox` fixture.
"""

from __future__ import annotations

import json

import pytest
from test_puntal_bench import run_measure

pytestmark = pytest.mark.usefixtures("no_real_backend")


def telemetry(tmp_path) -> list[dict]:
    return [
        json.loads(line)
        for line in (tmp_path / "work" / "telemetry.jsonl").read_text().splitlines()
    ]


def test_a_fast_session_is_coherent_and_mostly_takes_no_tool(tmp_path):
    assert run_measure(tmp_path, "calibrate", "--dry-run", "--puntal-path", "fast").returncode == 0
    ran = run_measure(tmp_path, "main", "--session", "1", "--dry-run", "--puntal-path", "fast")
    assert ran.returncode == 0, ran.stderr
    text = run_measure(tmp_path, "summarize").stdout
    assert "no contradictions found" in text
    assert "zero contradictions over persisted state: PASS" in text
    main = [r for r in telemetry(tmp_path) if r["labels"]["stage"] == "main"]
    assert {r["path"] for r in main} == {"fast"}, "every node of the bench declares its reads"
    assert all(r["tool_calls"] == [] and r["plan"]["applied"] is not None for r in main)
    assert "paths {'fast': 8}" in text


def test_the_calibration_tool_call_still_runs_through_the_slow_path_on_a_fast_bench(tmp_path):
    assert run_measure(tmp_path, "calibrate", "--dry-run", "--puntal-path", "fast").returncode == 0
    records = telemetry(tmp_path)
    assert [r["path"] for r in records] == ["fast", "slow"]
    assert records[1]["slow_path_reason"] and len(records[1]["tool_calls"]) == 1


@pytest.mark.parametrize(
    ("fault", "expected"),
    [
        ("accept_invalid_transition", "ticket_field"),
        ("lose_ticket", "ticket_missing"),
        ("wrong_count", "response_report_counts"),
    ],
)
def test_a_misbehaving_fast_puntal_is_caught_by_the_same_oracles(tmp_path, fault, expected):
    ran = run_measure(
        tmp_path,
        "main",
        "--session",
        "1",
        "--dry-run",
        "--puntal-path",
        "fast",
        "--fake-fault",
        fault,
    )
    assert ran.returncode == 0, ran.stderr
    text = run_measure(tmp_path, "summarize").stdout
    assert "CONTRADICTION" in text and expected in text


def test_a_summary_the_puntal_forgot_is_not_a_fault_on_the_fast_path(tmp_path):
    """The app derives the summary and allocates the ids: what the puntal cannot touch it cannot
    get wrong."""
    ran = run_measure(
        tmp_path,
        "main",
        "--session",
        "1",
        "--dry-run",
        "--puntal-path",
        "fast",
        "--fake-fault",
        "stale_summary",
    )
    assert ran.returncode == 0, ran.stderr
    assert (
        "zero contradictions over persisted state: PASS"
        in run_measure(tmp_path, "summarize").stdout
    )


def test_a_plan_the_executor_refuses_is_counted_by_the_summary(tmp_path):
    ran = run_measure(
        tmp_path,
        "main",
        "--session",
        "1",
        "--dry-run",
        "--puntal-path",
        "fast",
        "--fake-fault",
        "update_missing_ticket",
    )
    assert ran.returncode == 0, ran.stderr
    machine = json.loads(run_measure(tmp_path, "summarize", "--json").stdout)
    assert machine["paths"]["executor_refusals"] >= 1 and machine["paths"]["retried"] >= 1
