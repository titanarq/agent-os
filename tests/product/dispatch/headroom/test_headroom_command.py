"""`python -m agent_os.product.dispatch headroom`: can more work run at once right now?

Read-only. `gh` is replaced by a function returning the open issues; no network, no backend.
"""

from __future__ import annotations

import json

import pytest
import yaml
from compile_support import body, write_v2_config

from agent_os import issues, lib
from agent_os.product.dispatch import cli

WORKER_BUDGET = "<!-- budget: mechanical-qwen -->\n"


def issue(number: int, state: str, node_id: str, *, depends_on=(), touches=()) -> dict:
    text = body(node_id, depends_on=depends_on, touches=touches) + WORKER_BUDGET
    return {"number": number, "body": text, "labels": [{"name": f"status:{state}"}]}


def configure(tmp_path, *, max_parallel_issues: int | None, worker_slots: int):
    path = write_v2_config(tmp_path / "agents.yaml")
    data = yaml.safe_load(path.read_text())
    data["planner"]["max_parallel_issues"] = max_parallel_issues
    data["project"]["backends"]["qwen"]["slots"] = worker_slots
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


@pytest.fixture
def open_issues(monkeypatch, tmp_path):
    rows: list[dict] = []
    monkeypatch.setattr(issues, "gh_json", lambda *args, **kwargs: rows)
    monkeypatch.setattr(
        lib, "DEFAULT_AGENTS_CONFIG", configure(tmp_path, max_parallel_issues=2, worker_slots=2)
    )
    return rows


def configure_host(monkeypatch, tmp_path, *, max_parallel_issues: int | None, worker_slots: int):
    monkeypatch.setattr(
        lib,
        "DEFAULT_AGENTS_CONFIG",
        configure(tmp_path, max_parallel_issues=max_parallel_issues, worker_slots=worker_slots),
    )


def headroom_lines(capsys, *arguments: str) -> list[str]:
    assert cli.main(["headroom", *arguments]) == 0
    return capsys.readouterr().out.splitlines()


def test_a_host_that_is_not_v2_has_nothing_to_assess(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        lib, "DEFAULT_AGENTS_CONFIG", write_v2_config(tmp_path / "a.yaml", dispatch_by_node=False)
    )
    monkeypatch.setattr(issues, "gh_json", lambda *a, **k: pytest.fail("gh must not be called"))
    assert "not a v2 host" in "\n".join(headroom_lines(capsys))


def test_independent_ready_tickets_could_all_start_while_slots_are_free(open_issues, capsys):
    open_issues += [
        issue(7, "ready", "uc-a", touches=["app/a.py"]),
        issue(8, "ready", "uc-b", touches=["app/b.py"]),
    ]
    lines = headroom_lines(capsys)
    assert "#7  could start now" in lines
    assert "#8  could start now" in lines
    assert lines[-1] == "2 could start now; 0 wait only for the cap"


def test_a_ticket_clear_of_every_rule_but_the_cap_waits_only_for_the_cap(
    open_issues, monkeypatch, tmp_path, capsys
):
    configure_host(monkeypatch, tmp_path, max_parallel_issues=1, worker_slots=1)
    open_issues += [
        issue(3, "doing", "uc-a", touches=["app/a.py"]),
        issue(7, "ready", "uc-b", touches=["app/b.py"]),
    ]
    lines = headroom_lines(capsys)
    assert any(
        line.startswith("#7  waits only for the cap:") and "max_parallel_issues=1" in line
        for line in lines
    )
    assert lines[-1] == "0 could start now; 1 wait only for the cap"


def test_the_slots_of_a_backend_are_no_cap_the_driver_makes_one(
    open_issues, monkeypatch, tmp_path, capsys
):
    configure_host(monkeypatch, tmp_path, max_parallel_issues=None, worker_slots=1)
    open_issues += [issue(3, "doing", "uc-a"), issue(7, "ready", "uc-b")]
    lines = headroom_lines(capsys)
    assert "#7  could start now" in lines
    assert (
        lines[0]
        == "slots: 1 worker(s) running, no cap (planner.max_parallel_issues unset) (qwen 1)"
    )


def test_only_the_free_room_is_offered_to_the_ready_tickets(open_issues, capsys):
    open_issues += [
        issue(3, "doing", "uc-a", touches=["app/a.py"]),
        issue(7, "ready", "uc-b", touches=["app/b.py"]),
        issue(8, "ready", "uc-c", touches=["app/c.py"]),
    ]
    lines = headroom_lines(capsys)
    assert "#7  could start now" in lines
    assert any(line.startswith("#8  waits only for the cap") for line in lines)
    assert lines[-1] == "1 could start now; 1 wait only for the cap"


def test_an_open_dependency_is_the_reason_and_not_the_cap(open_issues, capsys):
    open_issues += [
        issue(3, "ready", "uc-a", touches=["app/a.py"]),
        issue(7, "ready", "uc-b", depends_on=["uc-a"], touches=["app/b.py"]),
    ]
    lines = headroom_lines(capsys)
    assert any(
        line.startswith("#7  waits: it depends on node `uc-a`") and "#3" in line for line in lines
    )
    assert lines[-1] == "1 could start now; 0 wait only for the cap; 1 wait for something else"


def test_a_clash_with_a_running_ticket_names_that_ticket(open_issues, capsys):
    open_issues += [
        issue(3, "doing", "uc-a", touches=["app"]),
        issue(7, "ready", "uc-b", touches=["app/b.py"]),
    ]
    line = next(line for line in headroom_lines(capsys) if line.startswith("#7"))
    assert line.startswith("#7  waits: it touches app/b.py, which running ticket #3 touches too")


def test_two_ready_tickets_on_the_same_code_are_not_both_counted_as_waiting_for_the_cap(
    open_issues, monkeypatch, tmp_path, capsys
):
    configure_host(monkeypatch, tmp_path, max_parallel_issues=1, worker_slots=1)
    open_issues += [
        issue(3, "doing", "uc-a", touches=["app/a.py"]),
        issue(7, "ready", "uc-b", touches=["app/shared.py"]),
        issue(8, "ready", "uc-c", touches=["app/shared.py"]),
    ]
    lines = headroom_lines(capsys)
    assert any(line.startswith("#7  waits only for the cap") for line in lines)
    assert any(line.startswith("#8  waits: it touches app/shared.py") for line in lines)
    assert lines[-1] == "0 could start now; 1 wait only for the cap; 1 wait for something else"


def test_the_summary_is_there_even_with_nothing_ready(open_issues, capsys):
    open_issues += [issue(3, "doing", "uc-a")]
    assert headroom_lines(capsys)[-1] == "0 could start now; 0 wait only for the cap"


def test_json_carries_the_same_verdicts(open_issues, capsys):
    open_issues += [
        issue(3, "ready", "uc-a", touches=["app/a.py"]),
        issue(7, "ready", "uc-b", depends_on=["uc-a"]),
    ]
    assert cli.main(["headroom", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    verdicts = {ticket["number"]: ticket["verdict"] for ticket in report["tickets"]}
    assert verdicts == {3: "could-start-now", 7: "waits"}
    assert report["could_start_now"] == [3]
    assert report["wait_only_for_the_cap"] == []
    assert report["max_parallel_issues"] == 2
