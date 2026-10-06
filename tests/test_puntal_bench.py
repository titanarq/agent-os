"""`bench/puntal/` -- the toy store, the reference model, the coherence analysis and the measurement
script's guards.

The bench is the one place real `claude -p` calls are authorised, so most of what is tested here is
that they cannot happen from a test: the script refuses without its opt-in flag, refuses under pytest,
refuses past the cap, and a dry run never touches the counter. The `no_real_backend` fixture is the
last wall -- a trap `claude` first on PATH and a check that the real counter file was not touched. The
end-to-end tests drive the whole script against `fake_claude.py`.

Pure filesystem and subprocess. This file must not request the `engine` or `db_sandbox` fixture.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from agent_os.cli import AGENT_OS_DIR
from agent_os.lib import load_agents_config

BENCH = AGENT_OS_DIR / "bench" / "puntal"
sys.path.insert(0, str(BENCH))

import analysis
import domain
import measure
import store as store_module

pytestmark = pytest.mark.usefixtures("no_real_backend")

MEASURE = BENCH / "measure.py"


# --- the toy store -----------------------------------------------------------------------------


def test_the_store_round_trips_documents_and_lists_them_in_natural_order(tmp_path):
    store = store_module.Store(tmp_path)
    for identifier in ("T-10", "T-2", "T-1"):
        store.put("tickets", identifier, {"id": identifier})
    assert [d["id"] for d in store.list("tickets")] == ["T-1", "T-2", "T-10"]
    assert store.get("tickets", "T-2") == {"id": "T-2"}
    assert store.list("nothing-here") == []
    assert list(store.dump()["tickets"]) == ["T-1", "T-2", "T-10"]
    assert store.dump()["_counters"] == {}


def test_update_merges_into_an_existing_document_only(tmp_path):
    store = store_module.Store(tmp_path)
    store.put("tickets", "T-1", {"id": "T-1", "status": "open"})
    assert store.update("tickets", "T-1", {"status": "in_progress"}) == {
        "id": "T-1",
        "status": "in_progress",
    }
    with pytest.raises(store_module.StoreError, match="not found"):
        store.update("tickets", "T-9", {"status": "x"})


def test_a_write_is_atomic_and_leaves_no_temporary_file(tmp_path):
    store = store_module.Store(tmp_path)
    store.put("tickets", "T-1", {"id": "T-1"})
    assert [p.name for p in (tmp_path / "tickets").iterdir()] == ["T-1.json"]


def test_the_counter_never_hands_the_same_number_to_two_processes(tmp_path):
    processes = [
        subprocess.Popen(
            [sys.executable, str(BENCH / "store.py"), "--dir", str(tmp_path), "next-id", "ticket"],
            stdout=subprocess.PIPE,
            text=True,
        )
        for _ in range(8)
    ]
    numbers = sorted(int(p.communicate()[0]) for p in processes)
    assert numbers == list(range(1, 9))
    assert store_module.Store(tmp_path).dump()["_counters"] == {"ticket": 8}


@pytest.mark.parametrize(
    "arguments",
    [
        ["get", "tickets", "T-9"],
        ["delete", "tickets", "T-9"],
        ["get", "../x", "T-1"],
        ["put", "tickets", "T 1", "{}"],
        ["put", "tickets", "T-1", "not json"],
        ["put", "tickets", "T-1", "[1]"],
    ],
)
def test_the_cli_fails_with_status_1_and_a_reason_on_stderr(tmp_path, arguments):
    ran = subprocess.run(
        [sys.executable, str(BENCH / "store.py"), "--dir", str(tmp_path), *arguments],
        capture_output=True,
        text=True,
        check=False,
    )
    assert ran.returncode == 1 and ran.stdout == "" and ran.stderr.startswith("store: ")


# --- the reference model -----------------------------------------------------------------------


def create(state, title="T", priority="normal"):
    return domain.apply_action(state, "create_ticket", {"title": title, "priority": priority})


def test_creating_a_ticket_takes_the_next_number_and_recounts_the_summary():
    state, first = create(domain.empty_state(), "  Printer  ", "high")
    state, second = create(state)
    assert first == {"ok": True, "ticket_id": "T-1", "status": "open"}
    assert second["ticket_id"] == "T-2"
    assert state["tickets"]["T-1"] == {
        "id": "T-1",
        "title": "Printer",
        "priority": "high",
        "status": "open",
        "resolution": None,
    }
    assert state["summary"]["board"] == {"open": 2, "in_progress": 0, "resolved": 0, "total": 2}
    assert state["_counters"] == {"ticket": 2}


@pytest.mark.parametrize(
    "payload, accepted",
    [
        ({"id": "T-1", "status": "in_progress"}, True),
        ({"id": "T-1", "status": "resolved", "note": "n"}, False),  # nothing is skipped
        ({"id": "T-1", "status": "open"}, False),
        ({"id": "T-9", "status": "in_progress"}, False),  # no such ticket
    ],
)
def test_the_life_of_a_ticket_only_moves_forward_one_status_at_a_time(payload, accepted):
    state, _ = create(domain.empty_state())
    after, expectation = domain.apply_action(state, "change_status", payload)
    assert expectation["ok"] is accepted
    assert (after == state) is (not accepted), "a refusal writes nothing"


def test_resolving_needs_a_note_and_records_it_and_resolved_is_final():
    state, _ = create(domain.empty_state())
    state, _ = domain.apply_action(state, "change_status", {"id": "T-1", "status": "in_progress"})
    refused, expectation = domain.apply_action(
        state, "change_status", {"id": "T-1", "status": "resolved", "note": "  "}
    )
    assert expectation["ok"] is False and refused == state
    state, expectation = domain.apply_action(
        state, "change_status", {"id": "T-1", "status": "resolved", "note": " Replaced it "}
    )
    assert expectation == {"ok": True, "ticket_id": "T-1", "status": "resolved"}
    assert state["tickets"]["T-1"]["resolution"] == "Replaced it"
    assert state["summary"]["board"]["resolved"] == 1
    again, expectation = domain.apply_action(
        state, "change_status", {"id": "T-1", "status": "in_progress"}
    )
    assert expectation["ok"] is False and again == state


def test_reads_change_nothing_and_expect_nothing():
    state, _ = create(domain.empty_state())
    for action in ("show_board", "board_report", "export_csv"):
        assert domain.apply_action(state, action, {}) == (state, None)


def reference_store():
    state = domain.empty_state()
    for payload in (
        {"title": "A", "priority": "high"},
        {"title": "B", "priority": "low"},
        {"title": "C", "priority": "high"},
    ):
        state, _ = domain.apply_action(state, "create_ticket", payload)
    state, _ = domain.apply_action(state, "change_status", {"id": "T-1", "status": "in_progress"})
    state, _ = domain.apply_action(
        state, "change_status", {"id": "T-1", "status": "resolved", "note": "done"}
    )
    return state


def test_a_store_the_rules_produced_satisfies_every_invariant():
    assert domain.check_invariants(reference_store()) == []
    assert domain.check_invariants(domain.empty_state()) == []


def broken(mutation):
    state = reference_store()
    mutation(state)
    return {violation.code for violation in domain.check_invariants(state)}


@pytest.mark.parametrize(
    "code, mutation",
    [
        ("summary_stale", lambda s: s["summary"]["board"].update(open=9)),
        ("summary_missing", lambda s: s["summary"].clear()),
        ("counter_mismatch", lambda s: s["_counters"].update(ticket=7)),
        ("ticket_ids_not_sequential", lambda s: s["tickets"].pop("T-2")),
        ("ticket_resolution", lambda s: s["tickets"]["T-1"].update(resolution=None)),
        ("ticket_resolution", lambda s: s["tickets"]["T-3"].update(resolution="but open")),
        ("ticket_status", lambda s: s["tickets"]["T-3"].update(status="done")),
        ("ticket_priority", lambda s: s["tickets"]["T-3"].update(priority="urgent")),
        ("ticket_title", lambda s: s["tickets"]["T-3"].update(title=" ")),
        ("ticket_id", lambda s: s["tickets"]["T-3"].update(id="T-4")),
    ],
)
def test_each_way_a_store_can_be_wrong_is_found(code, mutation):
    assert code in broken(mutation)


def test_diff_states_names_what_differs_and_ignores_fields_the_rules_do_not_mention():
    expected = reference_store()
    actual = json.loads(json.dumps(expected))
    actual["tickets"]["T-3"]["created_at"] = "today"
    assert domain.diff_states(expected, actual) == []
    actual["tickets"]["T-2"]["title"] = "other"
    actual["tickets"].pop("T-3")
    actual["_counters"]["ticket"] = 5
    assert {v.code for v in domain.diff_states(expected, actual)} == {
        "ticket_field",
        "ticket_missing",
        "counter_value",
    }


@pytest.mark.parametrize(
    "text, parsed",
    [
        ('{"a": 1}', {"a": 1}),
        ('```json\n{"a": 1}\n```', {"a": 1}),
        ('Here you go: {"a": 1} hope it helps', {"a": 1}),
        ("no json here", None),
        ("[1, 2]", None),
        ("", None),
    ],
)
def test_parse_response_tolerates_a_fence_and_prose_around_the_object(text, parsed):
    assert domain.parse_response(text) == parsed


def test_every_node_the_actions_are_bound_to_exists_and_the_gap_action_shares_a_described_nodes():
    for action in domain.ACTIONS:
        assert (BENCH / "nodes" / f"{domain.NODE_FOR_ACTION[action]}.md").is_file()
    assert (BENCH / "nodes" / "calibration.md").is_file()
    assert (BENCH / "nodes" / "calibration-tool.md").is_file()
    (gap,) = domain.GAP_ACTIONS
    assert domain.NODE_FOR_ACTION[gap] == domain.NODE_FOR_ACTION["show_board"]
    node = (BENCH / "nodes" / f"{domain.NODE_FOR_ACTION[gap]}.md").read_text()
    assert "export" not in node.lower() and "csv" not in node.lower(), "the gap must be real"
    for action in domain.ACTIONS:
        text = (BENCH / "nodes" / f"{domain.NODE_FOR_ACTION[action]}.md").read_text()
        assert "## Ancestor goals" in text and "## Use case" in text


# --- the numbers -------------------------------------------------------------------------------


def test_percentiles_are_nearest_rank_and_say_so():
    values = list(range(1, 25))  # n = 24
    assert analysis.percentile(values, 0.50) == 12
    assert analysis.percentile(values, 0.95) == 23, "the 23rd of 24: one outlier moves it"
    assert analysis.percentile([5], 0.95) == 5
    assert analysis.percentile([], 0.95) is None
    assert analysis.percentile([3, 1, 2], 0.5) == 2


def test_describe_skips_missing_measurements():
    assert analysis.describe([1.0, None, 3.0])["n"] == 2
    assert analysis.describe([None]) == {"n": 0}
    assert analysis.describe([1.0, 3.0])["mean"] == 2.0


def test_cache_report_says_how_much_was_read_from_the_cache():
    records = [
        {
            "usage": {
                "cache_read_input_tokens": 900,
                "cache_creation_input_tokens": 0,
                "input_tokens": 100,
            }
        }
    ]
    assert analysis.cache_report(records)["read_fraction"] == 0.9


# --- the coherence analysis, on traces written by hand -----------------------------------------

SCRIPT = [
    ("s1", "create_ticket", {"title": "A", "priority": "high"}),
    ("s1", "create_ticket", {"title": "B"}),
    ("s1", "change_status", {"id": "T-1", "status": "in_progress"}),
    ("s1", "change_status", {"id": "T-2", "status": "resolved", "note": "x"}),
    ("s1", "show_board", {}),
    ("s1", "export_csv", {}),
    ("s2", "show_board", {}),
    ("s2", "change_status", {"id": "T-1", "status": "resolved", "note": "done it"}),
    ("s2", "board_report", {}),
    ("s2", "export_csv", {}),
]


def reference_response(action, payload, before, after):
    _, expectation = domain.apply_action(before, action, payload)
    tickets = domain.tickets_of(after)
    if action == "create_ticket":
        return json.dumps({"ok": True, "ticket_id": expectation["ticket_id"]})
    if action == "change_status":
        if expectation["ok"]:
            return json.dumps({"ok": True, "ticket_id": payload["id"], "status": payload["status"]})
        return json.dumps({"ok": False, "ticket_id": payload["id"], "reason": "not allowed"})
    if action == "show_board":
        board = [
            {k: tickets[i][k] for k in ("id", "title", "priority", "status")}
            for i in domain.sorted_ticket_ids(after)
        ]
        return json.dumps({"tickets": board, "counts": domain.recount(after)})
    if action == "board_report":
        counts = domain.recount(after)
        return json.dumps(
            {
                "total": counts["total"],
                "counts": {k: counts[k] for k in domain.STATUSES},
                "oldest_unresolved": domain.oldest_unresolved(after),
                "high_priority_unresolved": domain.high_priority_unresolved(after),
            }
        )
    return "id,title\n" + "\n".join(f"{i},{tickets[i]['title']}" for i in tickets)


def build_trace(behave=None, respond=None, outcome=None, gap_note=None):
    """A trace of SCRIPT as a perfect puntal would leave it. `behave(seq, action, payload, before)`
    returns the store after an invocation, `respond(seq, ...)` its response text: a test replaces
    one to plant a defect, and every later invocation then starts from what the defect left."""
    state = domain.empty_state()
    trace, telemetry = [], {}
    for seq, (session, action, payload) in enumerate(SCRIPT, start=1):
        after = (
            behave(seq, action, payload, state)
            if behave
            else domain.apply_action(state, action, payload)[0]
        )
        if after is None:
            after = domain.apply_action(state, action, payload)[0]
        text = respond(seq, action, payload, state, after) if respond else None
        if text is None:
            text = reference_response(action, payload, state, after)
        invocation_id = f"inv-{seq}"
        trace.append(
            {
                "seq": seq,
                "invocation_id": invocation_id,
                "stage": "main",
                "session": session,
                "step": seq,
                "action": action,
                "payload": payload,
                "store_before": state,
                "store_after": after,
            }
        )
        telemetry[invocation_id] = {
            "invocation_id": invocation_id,
            "outcome": (outcome or {}).get(seq, "ok"),
            "response": text,
            "gap_note": (
                "asked for an export; the node does not describe it"
                if action in domain.GAP_ACTIONS
                else None
            )
            if gap_note is None
            else gap_note(seq, action),
            "tool_violations": [],
        }
        state = after
    return trace, telemetry


def found(report, kind=None, code=None):
    return [
        c
        for c in report.contradictions
        if (kind is None or c.kind == kind) and (code is None or c.code == code)
    ]


def test_a_trace_of_a_perfect_puntal_has_no_contradiction():
    trace, telemetry = build_trace()
    report = analysis.analyze_coherence(trace, telemetry)
    assert report.contradictions == [] and report.notes == []
    assert report.sessions == ["s1", "s2"] and report.invocations_checked == len(SCRIPT)
    assert (report.gap_notes_expected, report.gap_notes_found) == (2, 2)


def test_a_stale_summary_is_one_finding_with_how_long_it_lasted():
    def behave(seq, action, payload, before):
        after = domain.apply_action(before, action, payload)[0]
        if seq == 4:  # a refused change that nevertheless leaves the summary wrong
            after = json.loads(json.dumps(after))
            after["summary"]["board"]["open"] += 1
        return after

    report = analysis.analyze_coherence(*build_trace(behave=behave))
    (summary,) = found(report, "invariant", "summary_stale")
    assert summary.seq == 4 and summary.occurrences >= 3, "reads leave it as it was: one finding"


def test_a_summary_not_recounted_by_a_write_is_found_at_that_write():
    def behave(seq, action, payload, before):
        after = domain.apply_action(before, action, payload)[0]
        if seq == 2:  # the second create does not recount summary/board
            after["summary"]["board"] = before["summary"]["board"]
        return after

    report = analysis.analyze_coherence(*build_trace(behave=behave))
    (summary,) = found(report, "invariant", "summary_stale")
    assert summary.seq == 2


def test_an_id_reused_for_a_second_ticket_is_blamed_on_the_invocation_that_did_it():
    def behave(seq, action, payload, before):
        if seq == 2:  # files B under T-1, over A, and still bumps the counter
            after = domain.apply_action(before, action, payload)[0]
            after["tickets"] = {"T-1": {**after["tickets"]["T-2"], "id": "T-1"}}
            return after
        return None

    report = analysis.analyze_coherence(*build_trace(behave=behave))
    divergences = found(report, "state_divergence")
    assert divergences and all(c.seq == 2 for c in divergences)
    assert found(report, "invariant", "counter_mismatch")


def test_accepting_a_transition_the_node_refuses_is_found():
    def behave(seq, action, payload, before):
        if seq == 4:  # T-2 goes from open to resolved, skipping in_progress
            after = domain.apply_action(
                before, "change_status", {"id": "T-2", "status": "in_progress"}
            )[0]
            after["tickets"]["T-2"].update(status="resolved", resolution="x")
            after["summary"]["board"] = domain.recount(after)
            return after
        return None

    report = analysis.analyze_coherence(*build_trace(behave=behave))
    assert {c.seq for c in found(report, "state_divergence")} == {4}


def test_a_read_that_writes_is_a_state_divergence():
    def behave(seq, action, payload, before):
        if seq == 5:  # show_board deletes T-2
            after = json.loads(json.dumps(before))
            after["tickets"].pop("T-2")
            return after
        return None

    report = analysis.analyze_coherence(*build_trace(behave=behave))
    assert any(c.code == "ticket_missing" and c.seq == 5 for c in found(report, "state_divergence"))


def test_a_response_that_contradicts_the_store_is_found():
    def respond(seq, action, payload, before, after):
        if action == "board_report":
            counts = domain.recount(after)
            return json.dumps(
                {
                    "total": counts["total"],
                    "counts": {
                        "open": counts["open"] + 1,
                        "in_progress": counts["in_progress"],
                        "resolved": counts["resolved"],
                    },
                    "oldest_unresolved": domain.oldest_unresolved(after),
                    "high_priority_unresolved": domain.high_priority_unresolved(after),
                }
            )
        return None

    report = analysis.analyze_coherence(*build_trace(respond=respond))
    (contradiction,) = found(report, "response")
    assert contradiction.code == "response_report_counts" and contradiction.action == "board_report"


def test_a_response_that_is_not_json_is_found():
    def respond(seq, action, payload, before, after):
        return "Sure! Created it." if action == "create_ticket" else None

    report = analysis.analyze_coherence(*build_trace(respond=respond))
    assert {c.code for c in found(report, "response")} == {"response_not_json"}


def test_a_fact_established_in_one_session_that_is_gone_in_the_next_is_found_at_the_boundary():
    def behave(seq, action, payload, before):
        after = domain.apply_action(before, action, payload)[0]
        if seq == 6:  # the end of session 1 loses T-1 (and the counter), silently
            after = json.loads(json.dumps(after))
            after["tickets"].pop("T-1")
        return after

    report = analysis.analyze_coherence(*build_trace(behave=behave))
    assert found(report, "state_divergence", "ticket_missing"), "blamed on the invocation"
    # ... and independently of whose fault it was, session 2 starts without a fact session 1 set.
    assert any(
        c.code == "ticket_missing" and "T-1" in c.message for c in found(report, "cross_session")
    )


def test_a_board_that_forgets_an_earlier_session_is_a_cross_session_contradiction():
    def respond(seq, action, payload, before, after):
        if seq == 7:  # the first look in session 2 does not list T-2
            board = [
                {k: t[k] for k in ("id", "title", "priority", "status")}
                for i, t in domain.tickets_of(after).items()
                if i != "T-2"
            ]
            return json.dumps({"tickets": board, "counts": domain.recount(after)})
        return None

    report = analysis.analyze_coherence(*build_trace(respond=respond))
    assert found(report, "response", "response_board_ids")
    assert found(report, "cross_session", "response_board_ids")


def test_the_store_changing_between_two_invocations_is_found():
    trace, telemetry = build_trace()
    trace[6]["store_before"] = json.loads(json.dumps(trace[6]["store_before"]))
    trace[6]["store_before"]["tickets"]["T-1"]["title"] = "tampered"
    report = analysis.analyze_coherence(trace, telemetry)
    assert found(report, "store_changed_outside_invocation")


def test_a_failed_invocation_is_reported_once_and_does_not_cascade_through_the_ledger():
    def behave(seq, action, payload, before):
        if seq == 2:  # the run died after writing the ticket and before the counter
            after = domain.apply_action(before, action, payload)[0]
            after["_counters"]["ticket"] = 1
            return after
        return None

    trace, telemetry = build_trace(behave=behave, outcome={2: "timeout"})
    report = analysis.analyze_coherence(trace, telemetry)
    assert not found(report, "cross_session"), "the ledger resynced to the store after the failure"
    assert found(report, "state_divergence", "counter_value")


def test_an_invocation_with_no_telemetry_line_is_reported():
    trace, telemetry = build_trace()
    del telemetry["inv-3"]
    report = analysis.analyze_coherence(trace, telemetry)
    assert [c.seq for c in found(report, "harness", "no_telemetry")] == [3]


def test_gap_notes_are_expected_where_the_node_is_silent_and_only_there():
    def gap_note(seq, action):
        return "asked for X" if action == "show_board" else None

    report = analysis.analyze_coherence(*build_trace(gap_note=gap_note))
    assert (report.gap_notes_expected, report.gap_notes_found) == (2, 0)
    assert len(report.gap_notes_missing) == 2 and len(report.gap_notes_unexpected) == 2


def test_tool_violations_in_the_telemetry_are_listed_apart_from_the_state_findings():
    trace, telemetry = build_trace()
    telemetry["inv-6"]["tool_violations"] = ["tool 'Write' is not the persistence tool"]
    report = analysis.analyze_coherence(trace, telemetry)
    assert report.contradictions == []
    assert [c.seq for c in report.contract_violations] == [6]


def test_calibration_records_are_not_part_of_the_coherence_replay():
    trace, telemetry = build_trace()
    trace.insert(
        0,
        {
            "seq": 0,
            "invocation_id": "cal",
            "stage": "calibration",
            "session": "cal",
            "action": "calibrate",
            "payload": {},
            "store_before": {},
            "store_after": {},
        },
    )
    assert analysis.analyze_coherence(trace, telemetry).contradictions == []


# --- the guards on real calls ------------------------------------------------------------------


def run_measure(tmp_path, *arguments, environment=None, strip_pytest_marker=False):
    env = dict(os.environ if environment is None else environment)
    env["PUNTAL_BENCH_COUNTER_FILE"] = str(tmp_path / "counter.json")
    env["FAKE_PUNTAL_LATENCY"] = "0"
    if strip_pytest_marker:
        env.pop("PYTEST_CURRENT_TEST", None)
    return subprocess.run(
        [sys.executable, str(MEASURE), "--workdir", str(tmp_path / "work"), *arguments],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        cwd=AGENT_OS_DIR,
    )


def seed_counter(path, used):
    path.write_text(json.dumps({"calls": [{"n": i + 1} for i in range(used)]}))


def test_the_cap_is_thirty_and_is_the_sum_of_the_three_stages():
    assert measure.REAL_CALL_CAP == 30
    sessions = sum(len(steps) for steps in measure.SESSIONS.values())
    assert measure.CALIBRATION_CALLS + sessions + measure.RESERVE_MAX_PER_RUN == 30


def test_a_real_call_without_the_opt_in_flag_is_refused(tmp_path):
    ran = run_measure(tmp_path, "calibrate")
    assert ran.returncode != 0 and "--allow-real-calls" in ran.stderr
    assert not (tmp_path / "work" / "trace.jsonl").exists()
    assert not (tmp_path / "counter.json").exists()


def test_real_calls_are_refused_under_pytest_even_with_the_flag(tmp_path):
    assert os.environ.get("PYTEST_CURRENT_TEST")
    ran = run_measure(tmp_path, "calibrate", "--allow-real-calls")
    assert ran.returncode != 0 and "never run under pytest" in ran.stderr
    assert not (tmp_path / "counter.json").exists() and not (tmp_path / "work").exists()


def test_the_two_modes_contradict_each_other(tmp_path):
    ran = run_measure(tmp_path, "calibrate", "--allow-real-calls", "--dry-run")
    assert ran.returncode != 0 and "contradict" in ran.stderr


def test_the_call_past_the_cap_is_refused_and_not_counted(tmp_path):
    counter = tmp_path / "counter.json"
    seed_counter(counter, measure.REAL_CALL_CAP - 1)
    assert measure.reserve_real_call(counter, stage="main", invocation_id="last") == 30
    with pytest.raises(measure.CapReached, match="cap is 30"):
        measure.reserve_real_call(counter, stage="main", invocation_id="one-too-many")
    assert measure.real_calls_used(counter) == 30
    assert json.loads(counter.read_text())["calls"][-1]["invocation_id"] == "last"


def test_a_call_is_counted_before_it_is_made(tmp_path):
    counter = tmp_path / "counter.json"
    measure.reserve_real_call(counter, stage="calibration", invocation_id="inv")
    recorded = json.loads(counter.read_text())["calls"]
    assert recorded[0]["stage"] == "calibration" and recorded[0]["invocation_id"] == "inv"


def test_the_script_refuses_at_the_cap_before_it_launches_anything(tmp_path):
    """A subprocess without pytest's marker -- the only way to reach the real path from a test -- with
    the counter at the cap. The trap `claude` on PATH is what fails the test if the refusal is late."""
    seed_counter(tmp_path / "counter.json", measure.REAL_CALL_CAP)
    ran = run_measure(tmp_path, "calibrate", "--allow-real-calls", strip_pytest_marker=True)
    assert ran.returncode != 0 and "cap" in ran.stderr
    assert not (tmp_path / "work" / "trace.jsonl").exists()
    assert measure.real_calls_used(tmp_path / "counter.json") == measure.REAL_CALL_CAP


def test_a_stage_that_does_not_fit_in_what_is_left_is_refused_whole(tmp_path):
    seed_counter(tmp_path / "counter.json", 25)
    (tmp_path / "work").mkdir()
    (tmp_path / "work" / "trace.jsonl").write_text(
        "".join(
            json.dumps({"stage": "calibration", "driver_exit_code": 0, "step": i}) + "\n"
            for i in (1, 2)
        )
    )
    ran = run_measure(
        tmp_path, "main", "--session", "1", "--allow-real-calls", strip_pytest_marker=True
    )
    assert ran.returncode != 0 and "needs 8 real calls and only 5" in ran.stderr
    assert measure.real_calls_used(tmp_path / "counter.json") == 25


def test_a_dry_run_never_touches_the_counter(tmp_path):
    ran = run_measure(tmp_path, "calibrate", "--dry-run")
    assert ran.returncode == 0, ran.stderr
    assert not (tmp_path / "counter.json").exists()
    seed_counter(tmp_path / "counter.json", 12)
    before = (tmp_path / "counter.json").read_text()
    (tmp_path / "work" / "trace.jsonl").unlink()
    assert run_measure(tmp_path, "calibrate", "--dry-run").returncode == 0
    assert (tmp_path / "counter.json").read_text() == before


def test_status_reports_the_counter(tmp_path):
    seed_counter(tmp_path / "counter.json", 7)
    ran = run_measure(tmp_path, "status")
    assert "real calls counted: 7 of 30" in ran.stdout


def test_a_dry_run_uses_the_fake_and_a_real_run_never_inherits_it(tmp_path, monkeypatch):
    monkeypatch.setenv("PUNTAL_CLAUDE_BIN", "/some/stand-in")
    monkeypatch.setenv("FAKE_PUNTAL_FAULT", "hang")
    parser = measure.build_parser()
    dry = measure.Context(
        parser.parse_args(["--workdir", str(tmp_path), "calibrate", "--dry-run"]), mode="dry"
    )
    assert dry.environment()["PUNTAL_CLAUDE_BIN"] == str(measure.FAKE_BACKEND)
    assert measure.scrub_backend_overrides() == ["PUNTAL_CLAUDE_BIN", "FAKE_PUNTAL_FAULT"]
    real = measure.Context(
        parser.parse_args(["--workdir", str(tmp_path), "calibrate", "--allow-real-calls"]),
        mode="real",
    )
    environment = real.environment()
    assert "PUNTAL_CLAUDE_BIN" not in environment and "FAKE_PUNTAL_FAULT" not in environment
    assert "PUNTAL_BENCH_COUNTER_FILE" not in measure.scrub_backend_overrides()


def test_the_generated_config_loads_and_carries_the_overrides(tmp_path):
    args = measure.build_parser().parse_args(
        [
            "--workdir",
            str(tmp_path),
            "calibrate",
            "--dry-run",
            "--class-override",
            "max_context=64000",
            "--puntal-override",
            "timeout_seconds=45",
        ]
    )
    context = measure.Context(args, mode="dry")
    context.prepare()
    config = load_agents_config(context.config_file)
    assert config.classes["puntal"].max_context == 64000 and config.puntal.timeout_seconds == 45
    api = (AGENT_OS_DIR / config.puntal.persistence_api_file).resolve()
    assert api == (BENCH / "persistence_api.txt").resolve()


def test_the_fake_backend_rejects_a_flag_the_real_cli_does_not_have(tmp_path):
    ran = subprocess.run(
        [sys.executable, str(BENCH / "fake_claude.py"), "-p", "--no-such-flag"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert ran.returncode == 1 and "unknown option '--no-such-flag'" in ran.stderr


# --- the whole script, against the fake --------------------------------------------------------


def test_the_stages_run_end_to_end_and_the_summary_is_computed_from_the_raw_files(tmp_path):
    assert run_measure(tmp_path, "calibrate", "--dry-run").returncode == 0
    assert run_measure(tmp_path, "calibrate", "--dry-run").returncode != 0, "calibration runs once"
    early = run_measure(tmp_path, "main", "--session", "3", "--dry-run")
    assert early.returncode != 0 and "needs session s1" in early.stderr
    assert run_measure(tmp_path, "main", "--session", "1", "--dry-run").returncode == 0
    assert run_measure(tmp_path, "main", "--session", "2", "--dry-run").returncode == 0
    resumed = run_measure(tmp_path, "main", "--session", "2", "--dry-run")
    assert resumed.returncode != 0 and "already complete" in resumed.stderr
    probes = run_measure(tmp_path, "reserve", "--count", "2", "--dry-run", "--model", "other-model")
    assert probes.returncode == 0, probes.stderr

    summary = run_measure(tmp_path, "summarize")
    assert summary.returncode == 0, summary.stderr
    text = summary.stdout
    for section in (
        "READ THIS FIRST",
        "CALIBRATION",
        "MAIN STAGE (n=16",
        "COHERENCE",
        "GO / NO-GO",
        "RESERVE PROBES (n=2",
    ):
        assert section in text, section
    assert (
        "NOTIONAL" in text
        and "nearest-rank" in text
        and "Sample sizes: calibration 2, main 16, reserve 2" in text
    )
    assert "cold cache" in text and "warm cache" in text and "FIRST-TURN CONTEXT" in text
    assert "(calibrate_tool)" in text and "tool calls 1" in text
    assert "no contradictions found" in text
    assert "gap notes: 2/2" in text
    assert "zero contradictions over persisted state: PASS" in text
    assert "model other-model" in text

    raw = run_measure(tmp_path, "summarize", "--json")
    machine = json.loads(raw.stdout)
    assert machine["n"] == {"calibration": 2, "main": 16, "reserve": 2}
    assert machine["contradictions"] == [] and machine["latency"]["total"]["n"] == 16

    # The raw files are what the summary reads: both are append-only JSON lines, one per invocation.
    telemetry = [
        json.loads(line)
        for line in (tmp_path / "work" / "telemetry.jsonl").read_text().splitlines()
    ]
    trace = [
        json.loads(line) for line in (tmp_path / "work" / "trace.jsonl").read_text().splitlines()
    ]
    assert len(telemetry) == len(trace) == 20
    assert {t["invocation_id"] for t in telemetry} == {t["invocation_id"] for t in trace}
    assert not (tmp_path / "counter.json").exists(), "the whole dry run spent no real call"
    assert run_measure(tmp_path, "check-store").returncode == 0


@pytest.mark.parametrize(
    "fault, expected",
    [
        ("stale_summary", "summary_missing"),
        ("reuse_last_id", "ticket_missing"),
        ("accept_invalid_transition", "ticket_field"),
        ("lose_ticket", "ticket_missing"),
        ("wrong_count", "response_report_counts"),
    ],
)
def test_a_misbehaving_puntal_is_caught_end_to_end(tmp_path, fault, expected):
    ran = run_measure(tmp_path, "main", "--session", "1", "--dry-run", "--fake-fault", fault)
    assert ran.returncode == 0, ran.stderr
    text = run_measure(tmp_path, "summarize").stdout
    assert "CONTRADICTION" in text and expected in text
    assert "zero contradictions over persisted state: FAIL" in text


def test_a_puntal_that_reaches_for_a_file_tool_fails_the_contract_check(tmp_path):
    ran = run_measure(tmp_path, "main", "--session", "1", "--dry-run", "--fake-fault", "write_code")
    assert ran.returncode == 0, ran.stderr
    text = run_measure(tmp_path, "summarize").stdout
    assert "contract: 1 tool-call violations" in text
    assert "the puntal ran only ./state: FAIL" in text
    assert "contract_violation" in text


def test_a_missing_gap_note_is_reported_apart_from_the_contradictions(tmp_path):
    run_measure(tmp_path, "main", "--session", "1", "--dry-run", "--fake-fault", "no_gap_note")
    text = run_measure(tmp_path, "summarize").stdout
    assert "gap notes: 0/1" in text and "[gap_note/missing]" in text
    assert "zero contradictions over persisted state: PASS" in text


def test_a_workdir_that_already_holds_a_store_is_not_started_over(tmp_path):
    store_module.Store(tmp_path / "work" / "store").put("tickets", "T-1", {"id": "T-1"})
    ran = run_measure(tmp_path, "main", "--session", "1", "--dry-run")
    assert ran.returncode != 0 and "fresh --workdir" in ran.stderr


def test_summarize_refuses_a_workdir_nothing_was_measured_in(tmp_path):
    ran = run_measure(tmp_path, "summarize")
    assert ran.returncode != 0 and "nothing has been measured" in ran.stderr


# --- the free checks on the real CLI, and the stop on a systematic failure ---------------------


def stub_cli(tmp_path, *, listing, version_status=0, version_stderr=""):
    script = tmp_path / "stub-claude"
    help_file = tmp_path / "help.txt"
    help_file.write_text(listing)
    script.write_text(
        "#!/bin/sh\n"
        f'case "$1" in --help) cat {help_file};; *) '
        f'if [ {version_status} -ne 0 ]; then echo "{version_stderr}" >&2; exit {version_status}; fi; '
        'echo "9.9.9 (stub)";; esac\n'
    )
    script.chmod(0o755)
    return str(script)


def driver_flags():
    from agent_os import puntal

    return puntal.backend_flags(model="m", effort="low", max_cost_usd=0.25)


def test_preflight_passes_a_cli_that_lists_every_flag_and_accepts_their_values(tmp_path):
    flags = driver_flags()
    listing = " ".join(f.split("=", 1)[0] for f in flags if f.startswith("-"))
    assert measure.preflight_backend(stub_cli(tmp_path, listing=listing), flags) == "9.9.9 (stub)"


def test_preflight_names_a_flag_the_cli_no_longer_lists(tmp_path):
    flags = driver_flags()
    listing = " ".join(
        f.split("=", 1)[0] for f in flags if f.startswith("-") and f != "--safe-mode"
    )
    with pytest.raises(measure.Refusal, match="--safe-mode"):
        measure.preflight_backend(stub_cli(tmp_path, listing=listing), flags)


def test_preflight_surfaces_a_value_the_cli_rejects(tmp_path):
    flags = driver_flags()
    listing = " ".join(f.split("=", 1)[0] for f in flags if f.startswith("-"))
    cli = stub_cli(
        tmp_path, listing=listing, version_status=1, version_stderr="argument is invalid"
    )
    with pytest.raises(measure.Refusal, match="argument is invalid"):
        measure.preflight_backend(cli, flags)


def test_a_missing_cli_is_a_refusal_not_a_traceback(tmp_path):
    with pytest.raises(measure.Refusal, match="cannot run"):
        measure.preflight_backend(str(tmp_path / "nowhere"), driver_flags())


def test_two_failed_invocations_in_a_row_stop_a_stage_and_spend_nothing_more(tmp_path):
    ran = run_measure(tmp_path, "main", "--session", "1", "--dry-run", "--fake-fault", "crash")
    assert ran.returncode != 0 and "stopping after 2 failed invocation(s) in a row" in ran.stderr
    trace = (tmp_path / "work" / "trace.jsonl").read_text().splitlines()
    assert len(trace) == 2


def test_the_calibration_stops_at_its_first_failure(tmp_path):
    ran = run_measure(tmp_path, "calibrate", "--dry-run", "--fake-fault", "crash")
    assert ran.returncode != 0 and "stopping after 1 failed invocation(s)" in ran.stderr
    assert len((tmp_path / "work" / "trace.jsonl").read_text().splitlines()) == 1


def test_the_calibration_proves_the_persistence_tool_ran_and_stops_when_it_was_denied(tmp_path):
    ran = run_measure(tmp_path, "calibrate", "--dry-run", "--fake-fault", "deny_tool")
    assert ran.returncode != 0 and "the calibration's tool call did not run" in ran.stderr
    assert "1 denied by the CLI" in ran.stderr
    assert len((tmp_path / "work" / "trace.jsonl").read_text().splitlines()) == 2


def test_a_real_session_does_not_start_before_the_calibration_passed(tmp_path):
    ran = run_measure(
        tmp_path, "main", "--session", "1", "--allow-real-calls", strip_pytest_marker=True
    )
    assert ran.returncode != 0 and "run `calibrate` first" in ran.stderr
    assert not (tmp_path / "counter.json").exists()


def test_the_first_turn_is_the_context_floor_and_never_more_than_the_peak(tmp_path):
    assert run_measure(tmp_path, "calibrate", "--dry-run").returncode == 0
    records = [
        json.loads(line)
        for line in (tmp_path / "work" / "telemetry.jsonl").read_text().splitlines()
    ]
    cold, warm = (r["usage"] for r in records)
    assert (
        cold["first_turn"]["cache_creation_input_tokens"]
        > 0
        == cold["first_turn"]["cache_read_input_tokens"]
    )
    assert (
        warm["first_turn"]["cache_read_input_tokens"]
        > 0
        == warm["first_turn"]["cache_creation_input_tokens"]
    )
    for usage in (cold, warm):
        assert 0 < usage["context_tokens_first_turn"] <= usage["context_tokens_peak"]
    assert records[1]["tool_calls"][0]["command"] == "./state list tickets"
