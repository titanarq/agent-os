"""`python -m agent_os.product.dispatch start-gate`: the driver's last question before a start.

`gh` is replaced by a function returning issue rows; no network, no backend.
"""

from __future__ import annotations

import pytest
from compile_support import body, ticket_row, write_v2_config

from agent_os import issues, lib
from agent_os.product.dispatch import cli


@pytest.fixture
def backlog(monkeypatch, tmp_path):
    rows: list[dict] = []
    monkeypatch.setattr(issues, "gh_json", lambda *args, **kwargs: rows)
    monkeypatch.setattr(lib, "DEFAULT_AGENTS_CONFIG", write_v2_config(tmp_path / "agents.yaml"))
    return rows


def test_a_host_that_is_not_v2_is_never_asked_anything(monkeypatch, tmp_path):
    monkeypatch.setattr(
        lib, "DEFAULT_AGENTS_CONFIG", write_v2_config(tmp_path / "a.yaml", dispatch_by_node=False)
    )
    monkeypatch.setattr(issues, "gh_json", lambda *a, **k: pytest.fail("gh must not be called"))
    assert cli.main(["start-gate", "7", "3"]) == 0


def test_a_ticket_with_an_address_and_a_clear_road_may_start(backlog, capsys):
    backlog += [ticket_row(7, body("uc-a", touches=["app/a.py"]))]
    assert cli.main(["start-gate", "7"]) == 0
    assert capsys.readouterr().err == ""


def test_an_unaddressed_ticket_is_refused_with_its_number(backlog, capsys):
    backlog += [ticket_row(7, "no marker")]
    assert cli.main(["start-gate", "7"]) == 1
    assert "issue #7: it carries no node address" in capsys.readouterr().err


def test_a_ticket_on_code_a_running_one_touches_is_refused(backlog, capsys):
    backlog += [
        ticket_row(3, body("uc-a", touches=["app"])),
        ticket_row(7, body("uc-b", touches=["app/b.py"])),
    ]
    assert cli.main(["start-gate", "7", "3"]) == 1
    assert "running ticket #3" in capsys.readouterr().err
    assert cli.main(["start-gate", "7"]) == 0


def test_a_ticket_whose_dependency_is_still_open_is_refused(backlog, capsys):
    backlog += [ticket_row(3, body("uc-a")), ticket_row(7, body("uc-b", depends_on=["uc-a"]))]
    assert cli.main(["start-gate", "7"]) == 1
    assert "`uc-a`" in capsys.readouterr().err


def test_an_issue_that_is_not_open_is_refused(backlog, capsys):
    assert cli.main(["start-gate", "9"]) == 1
    assert "not an open issue" in capsys.readouterr().err
