"""A GitHub App that may not read CI checks: found by the doctor before the first run, and said in
one line by `issues.py move N review` when it is found the hard way. Every `gh` call is faked."""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from agent_os import doctor, issues
from agent_os.lib import ProjectConfig
from agent_os.product.tracker.app_check_access import CheckAccess, probe_check_access

REFUSED = "gh: Resource not accessible by integration (HTTP 403)"
RAW_GRAPHQL_REFUSAL = (
    "gh pr list --repo owner/name --state open failed:\n"
    "GraphQL: Resource not accessible by integration (repository.pullRequests.nodes.0.statusCheckRollup)"
)


def _completed(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(
        args=["x"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def _gh_refusing(*refused_endpoints, other_failure=None):
    """A fake `gh` that refuses the endpoints named, fails another with `other_failure` if given
    as `{endpoint: message}`, and answers everything else."""

    def run_gh(*args):
        endpoint = args[1].rsplit("/", 1)[-1]
        if endpoint in refused_endpoints:
            return _completed(returncode=1, stderr=REFUSED)
        if other_failure and endpoint in other_failure:
            return _completed(returncode=1, stderr=other_failure[endpoint])
        return _completed(stdout="{}")

    return run_gh


def test_an_app_that_may_read_both_checks_and_statuses_lacks_nothing():
    assert probe_check_access("owner/name", _gh_refusing()) == CheckAccess((), None)


def test_an_app_without_either_permission_is_reported_with_both_names():
    access = probe_check_access("owner/name", _gh_refusing("check-runs", "status"))
    assert access.lacking_permissions == ("Checks: read", "Commit statuses: read")
    assert access.unreadable_reason is None


def test_an_app_without_commit_statuses_is_reported_with_that_one_only():
    access = probe_check_access("owner/name", _gh_refusing("status"))
    assert access.lacking_permissions == ("Commit statuses: read",)


def test_a_failure_that_is_not_a_permission_refusal_is_not_blamed_on_the_permissions():
    gh = _gh_refusing(other_failure={"check-runs": "gh: Not Found (HTTP 404)"})
    access = probe_check_access("owner/name", gh)
    assert access.lacking_permissions == ()
    assert "Not Found" in access.unreadable_reason


def test_the_probe_reads_the_default_branch_head_and_nothing_else():
    asked = []

    def run_gh(*args):
        asked.append(args)
        return _completed(stdout="{}")

    probe_check_access("owner/name", run_gh)
    assert asked == [
        ("api", "repos/owner/name/commits/HEAD/check-runs"),
        ("api", "repos/owner/name/commits/HEAD/status"),
    ]


def test_move_review_says_in_one_line_that_the_app_cannot_read_checks():
    with (
        patch.object(issues, "gh_json", side_effect=SystemExit(RAW_GRAPHQL_REFUSAL)),
        pytest.raises(SystemExit) as refusal,
    ):
        issues.refuse_review_while_checks_are_not_green("owner/name", 7)
    message = str(refusal.value.code)
    assert "\n" not in message
    assert "GraphQL" not in message
    assert message.startswith("move #7 review refused:")
    assert "Checks: read" in message and "Commit statuses: read" in message
    assert "adoption/substrate.md step 14" in message


def test_move_review_keeps_any_other_gh_failure_as_it_was():
    with (
        patch.object(issues, "gh_json", side_effect=SystemExit("gh pr list failed:\nHTTP 502")),
        pytest.raises(SystemExit, match="HTTP 502"),
    ):
        issues.refuse_review_while_checks_are_not_green("owner/name", 7)


# ---- the doctor's check ---------------------------------------------------------------------


def _project(**overrides) -> ProjectConfig:
    fields = {
        "repo": "owner/name",
        "tracking_epic": 1,
        "board_number": 1,
        "planner_app": "acme-planner",
        "role_apps": {"validator": "acme-validator"},
    }
    fields.update(overrides)
    return ProjectConfig(**fields)


def _fake_subprocess(refusing_apps=(), unmintable_apps=()):
    """Dispatches the two commands the check runs: minting an App's token (token = `token-<slug>`)
    and `gh api ...` as whichever App the `GH_TOKEN` of the call belongs to. Returns the dispatcher
    and the list of `(slug, endpoint)` pairs it was asked."""
    asked = []

    def run(args, **kwargs):
        if "agent_os.gh_app_token" in args:
            slug = args[args.index("--app") + 1]
            if slug in unmintable_apps:
                return _completed(returncode=2, stderr=f"gh_app_token: no secrets file for {slug}")
            return _completed(stdout=f"token-{slug}\n")
        assert args[:2] == ["gh", "api"], args
        slug = kwargs["env"]["GH_TOKEN"].removeprefix("token-")
        asked.append((slug, args[2].rsplit("/", 1)[-1]))
        if slug in refusing_apps:
            return _completed(returncode=1, stderr=REFUSED)
        return _completed(stdout="{}")

    return run, asked


def test_the_doctor_passes_when_the_planner_and_the_validator_may_read_checks(tmp_path):
    run, asked = _fake_subprocess()
    with patch("subprocess.run", side_effect=run):
        check = doctor.check_apps_read_checks(_project(), tmp_path, "owner/name")
    assert check.ok
    assert "acme-planner" in check.detail and "acme-validator" in check.detail
    assert {slug for slug, _ in asked} == {"acme-planner", "acme-validator"}


def test_the_doctor_fails_naming_the_app_the_missing_permissions_and_the_remedy(tmp_path):
    run, _ = _fake_subprocess(refusing_apps={"acme-validator"})
    with patch("subprocess.run", side_effect=run):
        check = doctor.check_apps_read_checks(_project(), tmp_path, "owner/name")
    assert not check.ok
    assert "acme-validator" in check.detail
    assert "Checks: read" in check.detail and "Commit statuses: read" in check.detail
    assert "acme-planner" not in check.detail.split("--")[0]
    assert "accept" in check.detail and "adoption/substrate.md step 14" in check.detail
    assert "\n" not in check.line()


def test_one_app_that_is_both_planner_and_validator_is_probed_once(tmp_path):
    run, asked = _fake_subprocess()
    with patch("subprocess.run", side_effect=run):
        doctor.check_apps_read_checks(_project(role_apps={}), tmp_path, "owner/name")
    assert [slug for slug, _ in asked] == ["acme-planner", "acme-planner"]


def test_the_doctor_fails_when_a_token_cannot_be_minted(tmp_path):
    run, _ = _fake_subprocess(unmintable_apps={"acme-planner"})
    with patch("subprocess.run", side_effect=run):
        check = doctor.check_apps_read_checks(_project(), tmp_path, "owner/name")
    assert not check.ok
    assert "acme-planner" in check.detail and "no secrets file" in check.detail
