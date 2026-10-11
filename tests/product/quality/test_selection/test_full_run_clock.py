import json
import stat
from datetime import UTC, datetime, timedelta

import pytest
from selection_support import commit_all, make_repository, write_file

from agent_os.product.test_selection import cli
from agent_os.product.test_selection.clock.full_run_clock import (
    full_run_is_due,
    parse_last_full_run,
)

NOW = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("age", "due"),
    [
        (timedelta(hours=3, minutes=59), False),
        (timedelta(hours=4), True),
        (timedelta(hours=4, minutes=1), True),
    ],
)
def test_full_run_is_due_at_the_interval_boundary(age, due):
    clock = full_run_is_due(NOW - age, NOW, 4)
    assert clock.due is due
    assert "(interval 4 h)" in clock.reason and " old " in clock.reason


def test_never_and_unknown_are_due_with_their_own_reasons():
    assert parse_last_full_run("never") is None and parse_last_full_run("unknown") is None
    assert full_run_is_due(None, NOW, 4).due is True


def test_a_naive_or_malformed_instant_is_refused():
    with pytest.raises(ValueError, match="timezone"):
        parse_last_full_run("2026-10-11T08:00:00")
    with pytest.raises(ValueError, match="ISO 8601"):
        parse_last_full_run("yesterday")
    assert parse_last_full_run("2026-10-11T08:00:00Z") == NOW - timedelta(hours=4)


def install_fake_gh(tmp_path, monkeypatch, stdout, exit_code=0):
    binary = tmp_path / "fakebin"
    binary.mkdir()
    gh = binary / "gh"
    gh.write_text(f"#!/bin/sh\ncat <<'EOF_PAYLOAD'\n{stdout}\nEOF_PAYLOAD\nexit {exit_code}\n")
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{binary}:/usr/bin:/bin")


def last_full_run(capsys):
    code = cli.main(["last-full-run", "--repo", "o/r"])
    captured = capsys.readouterr()
    return code, captured.out.strip(), captured.err


@pytest.mark.parametrize(
    ("payload", "exit_code", "expected"),
    [
        ('{"artifacts": []}', 0, "never"),
        (
            '{"artifacts": [{"created_at": "2026-10-11T08:00:00Z", "expired": false}]}',
            0,
            "2026-10-11T08:00:00Z",
        ),
        ('{"artifacts": [{"created_at": "2026-10-09T08:00:00Z", "expired": true}]}', 0, "never"),
        ("not json", 0, "unknown"),
        ('{"other": 1}', 0, "unknown"),
        ('{"artifacts": [{"created_at": "soon", "expired": false}]}', 0, "unknown"),
        ("", 1, "unknown"),
    ],
)
def test_last_full_run_reads_the_newest_unexpired_artifact(
    tmp_path, monkeypatch, capsys, payload, exit_code, expected
):
    install_fake_gh(tmp_path, monkeypatch, payload, exit_code)
    code, out, err = last_full_run(capsys)
    assert (code, out) == (0, expected)
    assert (expected == "unknown") == bool(err)


def test_last_full_run_is_unknown_when_gh_is_not_installed(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("PATH", str(tmp_path))
    assert last_full_run(capsys)[:2] == (0, "unknown")


@pytest.fixture
def repository(tmp_path):
    root = make_repository(tmp_path)
    write_file(root, "bin/worker.sh", "changed\n")
    commit_all(root)
    return root


def plan_json(repository, capsys, *extra):
    cli.main(
        ["--root", str(repository), "plan", "--base", "main", "--manifest", "manifest.yaml"]
        + ["--format", "json", *extra]
    )
    return json.loads(capsys.readouterr().out)


def test_plan_under_the_clock_in_its_four_cases(repository, capsys):
    fresh = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    stale = (datetime.now(UTC) - timedelta(hours=5)).isoformat()
    assert plan_json(repository, capsys)["mode"] == "selected"
    assert plan_json(repository, capsys, "--last-full-run", fresh)["mode"] == "selected"
    due = plan_json(repository, capsys, "--last-full-run", stale)
    assert due["mode"] == "full" and "is 5 h" in due["reason"] and "interval 4 h" in due["reason"]
    assert plan_json(repository, capsys, "--last-full-run", "never")["mode"] == "full"
    assert plan_json(repository, capsys, "--last-full-run", "unknown")["mode"] == "full"
    only = ("--only-when-due", "--last-full-run")
    assert plan_json(repository, capsys, *only, fresh)["mode"] == "none"
    assert plan_json(repository, capsys, *only, stale)["mode"] == "full"
    assert plan_json(repository, capsys, "--interval-hours", "0.5", *only, fresh)["mode"] == "full"


def test_run_publishes_the_mode_and_execs_nothing_when_none(
    repository, tmp_path, monkeypatch, capsys
):
    output, summary = tmp_path / "output", tmp_path / "summary"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    fresh = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    marker = tmp_path / "ran"
    command = f"touch {marker}"
    base = ["--root", str(repository), "run", "--base", "main", "--manifest", "manifest.yaml"]
    assert cli.main([*base, "--command", command, "--only-when-due", "--last-full-run", fresh]) == 0
    assert output.read_text() == "mode=none\n" and not marker.exists()
    assert cli.main([*base, "--command", command, "--last-full-run", "never"]) == 0
    assert output.read_text() == "mode=none\nmode=full\n" and marker.exists()
    assert "mode: full" in summary.read_text()
