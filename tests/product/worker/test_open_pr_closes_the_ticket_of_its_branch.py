"""`open-pr` closes the ticket the branch was worked for, and reuses a pull request that exists (#230).

Seen in a host rollout: `open-pr` wrote `Closes #116` on the pull request of #138, because the slot's
recorded issue was a stale one; elsewhere it gave up on `gh pr create` when a pull request of the
branch already existed but `gh pr list` had not shown it.

The harness is `test_worker_task.py`'s own: a worktree with a real local origin and a stub `gh`.
"""

from __future__ import annotations

from pathlib import Path

from test_worker_task import _git, _open_pr, worker_at_its_end  # noqa: F401


def rename_the_branch(worktree, name):
    _git("branch", "-m", name, cwd=worktree)


def stub_where_the_listing_misses_an_existing_pull_request(environment):
    stub = Path(environment["PATH"].split(":")[0]) / "gh"
    source = stub.read_text()
    source = source.replace(
        'out("7" if "pr\\tcreate" in previous else "")',
        'out("")',
    )
    source = source.replace(
        'if args[:2] == ["pr", "create"]:\n    out("https://github.com/owner/name/pull/7")',
        'if args[:2] == ["pr", "create"]:\n'
        '    print("a pull request for branch already exists", file=sys.stderr)\n'
        "    sys.exit(1)\n"
        'if args[:2] == ["pr", "view"] and "--json\tnumber,state" in "\t".join(args):\n    out("7")',
    )
    stub.write_text(source)


def test_the_pull_request_closes_the_issue_the_branch_names_not_a_stale_recorded_one(
    worker_at_its_end,  # noqa: F811
):
    environment, worktree, _remote, cache, calls = worker_at_its_end
    (cache / "worker_claude.issue").write_text("116\n")
    rename_the_branch(worktree, "claude/348-pr")

    result = _open_pr(environment)

    assert result.returncode == 0, result.stdout + result.stderr
    created = [line for line in calls.read_text().splitlines() if line.startswith("pr\tcreate")]
    assert len(created) == 1
    assert "Closes #348" in created[0], created[0]
    assert "Closes #116" not in created[0]


def test_a_branch_without_a_ticket_number_keeps_the_recorded_issue(worker_at_its_end):  # noqa: F811
    environment, worktree, _remote, cache, calls = worker_at_its_end
    (cache / "worker_claude.issue").write_text("116\n")
    rename_the_branch(worktree, "claude/no-number")

    assert _open_pr(environment).returncode == 0
    created = [line for line in calls.read_text().splitlines() if line.startswith("pr\tcreate")]
    assert "Closes #116" in created[0], created[0]


def test_a_pull_request_that_the_listing_missed_is_reused_not_reported_as_a_failure(
    worker_at_its_end,  # noqa: F811
):
    environment, _worktree, _remote, _cache, _calls = worker_at_its_end
    stub_where_the_listing_misses_an_existing_pull_request(environment)

    result = _open_pr(environment)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "gh pr create failed" not in result.stdout
    assert "PR #7 is already open" in result.stdout
