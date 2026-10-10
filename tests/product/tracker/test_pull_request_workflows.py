"""`agent_os.doctor.check_pull_request_ci` and the workflow reading behind it: at least one workflow
must fire on `pull_request` with no path filter, or a host-only PR reports zero checks
(agent-os#50). Moved here with the reading itself; filesystem only."""

from __future__ import annotations

from agent_os import doctor


def _workflow(root, name, text):
    path = root / ".github" / "workflows" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


PATH_FILTERED = "on:\n  pull_request:\n    paths:\n      - agent_os/**\njobs: {}\n"


def test_check_pull_request_ci_fails_with_no_workflow_at_all(tmp_path):
    check = doctor.check_pull_request_ci(tmp_path)
    assert not check.ok
    assert "agent-os-install" in check.detail


def test_check_pull_request_ci_fails_when_every_workflow_is_path_filtered(tmp_path):
    _workflow(tmp_path, "ci-agent-os.yml", PATH_FILTERED)
    _workflow(tmp_path, "docs.yml", "on:\n  pull_request:\n    paths-ignore: ['src/**']\n")
    _workflow(tmp_path, "nightly.yml", "on:\n  schedule:\n    - cron: '0 0 * * *'\n")
    check = doctor.check_pull_request_ci(tmp_path)
    assert not check.ok
    assert "condition 1" in check.detail


def test_check_pull_request_ci_passes_on_an_unfiltered_pull_request_trigger(tmp_path):
    _workflow(tmp_path, "ci-agent-os.yml", PATH_FILTERED)
    _workflow(tmp_path, "ci.yml", "on:\n  pull_request:\n    branches: [main]\njobs: {}\n")
    check = doctor.check_pull_request_ci(tmp_path)
    assert check.ok, check.detail
    assert "ci.yml" in check.detail


def test_check_pull_request_ci_reads_the_string_and_list_trigger_forms(tmp_path):
    _workflow(tmp_path, "a.yml", "on: pull_request\n")
    assert doctor.check_pull_request_ci(tmp_path).ok
    _workflow(tmp_path, "a.yml", "on: [push, pull_request]\n")
    assert doctor.check_pull_request_ci(tmp_path).ok


def test_check_pull_request_ci_fails_rather_than_crashes_on_an_unreadable_workflow(tmp_path):
    _workflow(tmp_path, "broken.yaml", "on: [unclosed\n")
    assert not doctor.check_pull_request_ci(tmp_path).ok
