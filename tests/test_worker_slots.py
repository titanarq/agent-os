"""More than one worker per backend: slots, separate from backends (agent-os#90).

A backend is a CLI plus its quota; a SLOT is one concurrent worker on it -- a PID, a worktree and
a branch. `project.backends.<name>.slots` (default 1) says how many; slot 1 is exactly the paths a
backend has always had, and slot N > 1 derives `<worktree>-N` and `.cache/worker_<backend>-N.*`.
`worker_task.sh <backend> start` picks the first free slot itself, so the planner keeps
dispatching by backend.

These tests drive the real `worker_task.sh` with a stub `gh` and a fake `claude`/`qwen` first on
`PATH` (the fakes never exit, so a launched run stays alive until the test stops it by PID through
the driver's own `stop`): no real backend is ever reachable from here.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

import pytest
from conftest import EXAMPLE_CONFIG
from pydantic import ValidationError
from test_agent_guard import VALID_BODY as GUARD_VALID_BODY
from test_agent_guard import _assistant_event, _rate_limit_event, _task_class
from test_worker_task import (
    DRIVER,
    GH_STUB_FULL,
    NEVER_EXITS_BACKEND_STUB,
    ROOT,
    VALID_BODY,
    _events_of_kind,
    _git,
    _planner_lock_held,
    _staged_environment,
    _subjects,
    _wait_until,
)

from agent_os import doctor
from agent_os import guard as agent_guard
from agent_os.lib import ProjectConfig, worker_slot_key, worker_slot_worktree, worker_slots

SLOTTED_BACKEND = "claude"


def _config_with_claude_slots(tmp_path, *, slots, max_parallel_issues, worktree):
    """`config.example.yaml` with the claude backend's worktree pointed at `worktree` (absolute, so
    it resolves the same from any root), `slots: <slots>` added to it, and the global cap patched."""
    text = EXAMPLE_CONFIG.read_text()
    patched, count = re.subn(
        r"(    claude:\n      worktree: )\S+\n",
        rf"\g<1>{worktree}\n      slots: {slots}\n",
        text,
    )
    assert count == 1, "config.example.yaml's claude backend changed shape"
    patched, count = re.subn(
        r"max_parallel_issues:\s*\d+", f"max_parallel_issues: {max_parallel_issues}", patched
    )
    assert count == 1
    path = tmp_path / "agents-slots.yaml"
    path.write_text(patched)
    return path


def _plain_worktree(path):
    path.mkdir()
    _git("init", "-q", "-b", "main", cwd=path)
    _git("config", "user.email", "worker@example.invalid", cwd=path)
    _git("config", "user.name", "worker", cwd=path)
    (path / "README.md").write_text("base\n")
    _git("add", "README.md", cwd=path)
    _git("commit", "-qm", "base", cwd=path)
    return path


def _slotted_environment(tmp_path, *, slots=2, max_parallel_issues=2, labels_by_issue):
    """Two (or more) plain git worktrees at `<base>` and `<base>-N`, the derivation slot N uses, and
    a config whose claude backend declares `slots`. No `WORKER_WORKTREE`: the slot's own worktree
    is the point."""
    base = tmp_path / "wt-claude"
    worktrees = [_plain_worktree(base)]
    for slot in range(2, slots + 1):
        worktrees.append(_plain_worktree(tmp_path / f"wt-claude-{slot}"))
    config_path = _config_with_claude_slots(
        tmp_path, slots=slots, max_parallel_issues=max_parallel_issues, worktree=base
    )
    cache = tmp_path / "cache"
    cache.mkdir()
    binaries = tmp_path / "bin"
    binaries.mkdir()
    for name, contents in (
        ("gh", GH_STUB_FULL),
        ("claude", NEVER_EXITS_BACKEND_STUB),
        ("qwen", NEVER_EXITS_BACKEND_STUB),
    ):
        stub = binaries / name
        stub.write_text(contents)
        stub.chmod(0o755)
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in ("WORKER_WORKTREE", "WORKER_SLOT")
    }
    environment.update(
        PATH=f"{binaries}:{environment['PATH']}",
        WORKER_CACHE_DIR=str(cache),
        AGENTS_CONFIG_PATH=str(config_path),
        AGENT_OS_GH_REPO="owner/name",
        GH_STUB_BODY=VALID_BODY,
        GH_STUB_LABELS_JSON=json.dumps(labels_by_issue),
        GH_TOKEN="stub-token-so-no-app-is-minted",
    )
    return environment, cache, worktrees


def _driver(environment, *arguments, backend=SLOTTED_BACKEND):
    return subprocess.run(
        ["bash", str(DRIVER), backend, *arguments],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def _stop_every_slot(environment, slots):
    for slot in range(1, slots + 1):
        _driver(environment, "stop", "--slot", str(slot))


def _pid_alive(pidfile):
    if not pidfile.is_file():
        return False
    try:
        os.kill(int(pidfile.read_text().strip()), 0)
    except (ProcessLookupError, ValueError):
        return False
    return True


def _cache_files(cache):
    return sorted(path.name for path in cache.iterdir() if path.is_file())


# ---- the reproduction: two workers on one backend -----------------------------------------------


def test_two_starts_on_one_backend_with_two_slots_run_in_two_worktrees(tmp_path):
    environment, cache, worktrees = _slotted_environment(
        tmp_path, labels_by_issue={"347": ["module:workers"], "348": ["module:prices"]}
    )
    try:
        first = _driver(environment, "start", "347")
        assert first.returncode == 0, first.stdout + first.stderr
        assert "started pid" in first.stdout
        second = _driver(environment, "start", "348")
        assert second.returncode == 0, second.stdout + second.stderr
        assert "started pid" in second.stdout

        # Slot 1 keeps the backend's own names; slot 2 has names of its own -- neither clobbered.
        assert (cache / "worker_claude.issue").read_text().strip() == "347"
        assert (cache / "worker_claude-2.issue").read_text().strip() == "348"
        assert _pid_alive(cache / "worker_claude.pid")
        assert _pid_alive(cache / "worker_claude-2.pid")
        assert (cache / "worker_claude.pid").read_text() != (
            cache / "worker_claude-2.pid"
        ).read_text()
        assert f"worktree:  {worktrees[0]} " in first.stdout
        assert f"worktree:  {worktrees[1]} " in second.stdout
        # The slot the run belongs to is recorded, so every later subcommand can find it.
        assert (cache / "worker_claude.state").read_text().startswith("STARTED")
        assert (cache / "worker_claude-2.state").read_text().startswith("STARTED")
    finally:
        _stop_every_slot(environment, 2)


def test_a_second_start_sharing_a_module_label_is_refused_as_it_is_today(tmp_path):
    environment, cache, _ = _slotted_environment(
        tmp_path, labels_by_issue={"347": ["module:workers"], "348": ["module:workers"]}
    )
    try:
        first = _driver(environment, "start", "347")
        assert first.returncode == 0, first.stdout + first.stderr
        before = _cache_files(cache)
        second = _driver(environment, "start", "348")
        assert second.returncode == 1
        assert "shares module label" in second.stdout
        assert "#347" in second.stdout
        assert not any(name.startswith("worker_claude-2.") for name in _cache_files(cache))
        assert _cache_files(cache) == before
    finally:
        _stop_every_slot(environment, 2)


def test_a_third_start_with_every_slot_busy_is_refused_and_writes_nothing(tmp_path):
    environment, cache, _ = _slotted_environment(
        tmp_path,
        max_parallel_issues=3,
        labels_by_issue={
            "347": ["module:workers"],
            "348": ["module:prices"],
            "349": ["module:reports"],
        },
    )
    try:
        assert _driver(environment, "start", "347").returncode == 0
        assert _driver(environment, "start", "348").returncode == 0
        before = {name: (cache / name).read_bytes() for name in _cache_files(cache)}
        third = _driver(environment, "start", "349")
        assert third.returncode == 1
        assert "every slot of backend 'claude' is busy" in third.stdout
        after = {name: (cache / name).read_bytes() for name in _cache_files(cache)}
        assert after == before
    finally:
        _stop_every_slot(environment, 2)


def test_the_global_cap_counts_the_other_slots_of_the_same_backend(tmp_path):
    environment, cache, _ = _slotted_environment(
        tmp_path,
        max_parallel_issues=1,
        labels_by_issue={"347": ["module:workers"], "348": ["module:prices"]},
    )
    try:
        assert _driver(environment, "start", "347").returncode == 0
        second = _driver(environment, "start", "348")
        assert second.returncode == 1
        assert "max_parallel_issues=1" in second.stdout
        assert not (cache / "worker_claude-2.issue").exists()
    finally:
        _stop_every_slot(environment, 2)


# ---- addressing a slot after the start ---------------------------------------------------------


def test_status_without_a_slot_reports_every_slot_and_with_one_reports_that_one(tmp_path):
    environment, _, _ = _slotted_environment(
        tmp_path, labels_by_issue={"347": ["module:workers"], "348": ["module:prices"]}
    )
    try:
        assert _driver(environment, "start", "347").returncode == 0
        every = _driver(environment, "status")
        assert every.returncode == 0, every.stdout + every.stderr
        assert "=== claude slot 1" in every.stdout
        assert "=== claude slot 2" in every.stdout
        assert "issue:     #347" in every.stdout
        one = _driver(environment, "status", "--slot", "2")
        assert "not running" in one.stdout
        assert "#347" not in one.stdout
    finally:
        _stop_every_slot(environment, 2)


def test_a_subcommand_that_needs_one_slot_refuses_to_guess_between_several(tmp_path):
    environment, _, _ = _slotted_environment(tmp_path, labels_by_issue={})
    result = _driver(environment, "stop")
    assert result.returncode == 2
    assert "--slot" in result.stdout


def test_a_slot_outside_the_configured_range_is_a_usage_error(tmp_path):
    environment, _, _ = _slotted_environment(tmp_path, labels_by_issue={})
    result = _driver(environment, "status", "--slot", "3")
    assert result.returncode == 2
    assert "slot 3" in result.stdout


def test_resume_by_issue_finds_the_slot_that_recorded_it(tmp_path):
    environment, cache, worktrees = _slotted_environment(tmp_path, labels_by_issue={})
    # A run of #348 that was cut on slot 2 and nothing on slot 1.
    (cache / "worker_claude-2.issue").write_text("348\n")
    (cache / "worker_claude-2.brief.md").write_text("brief\n")
    (cache / "worker_claude-2.state").write_text("CUT_BY_GUARD reason=stall\n")
    try:
        result = _driver(environment, "resume", "--issue", "348")
        assert result.returncode == 0, result.stdout + result.stderr
        assert f"worktree:  {worktrees[1]} " in result.stdout
        assert _pid_alive(cache / "worker_claude-2.pid")
        assert not (cache / "worker_claude.pid").exists()
    finally:
        _stop_every_slot(environment, 2)


def test_resume_by_an_issue_no_slot_recorded_is_refused_and_writes_nothing(tmp_path):
    environment, cache, _ = _slotted_environment(tmp_path, labels_by_issue={})
    (cache / "worker_claude-2.issue").write_text("348\n")
    before = _cache_files(cache)
    result = _driver(environment, "resume", "--issue", "999")
    assert result.returncode == 1
    assert "#999" in result.stdout
    assert _cache_files(cache) == before


def test_resume_without_a_slot_or_an_issue_refuses_to_guess(tmp_path):
    environment, _, _ = _slotted_environment(tmp_path, labels_by_issue={})
    result = _driver(environment, "resume")
    assert result.returncode == 2
    assert "--issue" in result.stdout


def test_branch_then_start_land_on_the_same_free_slot(tmp_path):
    environment, cache, worktrees = _slotted_environment(
        tmp_path, labels_by_issue={"347": ["module:workers"], "348": ["module:prices"]}
    )
    # A local origin so `branch` can fetch `origin/main` the way the planner's dispatch does.
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    for worktree in worktrees:
        _git("remote", "add", "origin", str(remote), cwd=worktree)
    _git("push", "-q", "origin", "main", cwd=worktrees[0])
    try:
        assert _driver(environment, "start", "347").returncode == 0
        branched = _driver(environment, "branch", "task/348-prices")
        assert branched.returncode == 0, branched.stdout + branched.stderr
        assert str(worktrees[1]) in branched.stdout
        started = _driver(environment, "start", "348")
        assert started.returncode == 0, started.stdout + started.stderr
        assert f"worktree:  {worktrees[1]} (task/348-prices" in started.stdout
        assert (cache / "worker_claude-2.issue").read_text().strip() == "348"
    finally:
        _stop_every_slot(environment, 2)


@pytest.mark.parametrize("subcommand", ["stop", "status", "freeze"])
def test_a_one_slot_backend_needs_no_slot_and_accepts_slot_one(tmp_path, subcommand):
    environment, _, _ = _slotted_environment(tmp_path, slots=1, labels_by_issue={})
    arguments = [subcommand] + (["why"] if subcommand == "freeze" else [])
    assert _driver(environment, *arguments).returncode == 0
    assert _driver(environment, *arguments, "--slot", "1").returncode == 0


# ---- the guard: (backend, slot) pairs, one quota verdict per backend ----------------------------


def _two_live_claude_slots(tmp_path, monkeypatch, *, events_by_slot):
    """Two live claude slots in the guard's eyes: slot 2's worktree configured beside slot 1's,
    liveness and the issue read stubbed, and the cut recorded instead of reaching the driver."""
    cache = tmp_path / ".cache"
    cache.mkdir()
    worktrees = {1: tmp_path / "example-claude", 2: tmp_path / "example-claude-2"}
    for worktree in worktrees.values():
        worktree.mkdir()
    monkeypatch.setenv("WORKER_CACHE_DIR", str(cache))
    monkeypatch.delenv("WORKER_WORKTREE", raising=False)
    monkeypatch.setattr(agent_guard, "BACKEND_WORKTREES", {"claude": str(worktrees[1])})
    monkeypatch.setattr(agent_guard, "EXTRA_SLOT_WORKTREES", {("claude", 2): str(worktrees[2])})
    monkeypatch.setattr(agent_guard, "BACKENDS", ("claude",))
    for slot, events in events_by_slot.items():
        key = "claude" if slot == 1 else f"claude-{slot}"
        (cache / f"worker_{key}.state").write_text("STARTED\n")
        (cache / f"worker_{key}.issue").write_text(f"{365 + slot}\n")
        (cache / f"worker_{key}.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
    body = f"{GUARD_VALID_BODY}\n\n<!-- budget: mechanical-claude -->"
    monkeypatch.setattr(
        agent_guard.subprocess,
        "run",
        lambda cmd, **kwargs: subprocess.CompletedProcess(cmd, 0, stdout=body, stderr=""),
    )
    monkeypatch.setattr(agent_guard, "_is_alive", lambda pidfile: True)
    monkeypatch.setattr(agent_guard, "_commit_timestamps", lambda tree, startref: [])
    monkeypatch.setattr(
        agent_guard,
        "load_task_classes",
        lambda: {"mechanical-claude": _task_class(qwen_fallback_eligible=True)},
    )
    cuts: list[tuple[str, str, int, str]] = []

    def cut_run(backend, reason, *, worktree, statefile, main, slot=1):
        cuts.append((backend, reason, slot, str(worktree)))

    monkeypatch.setattr(agent_guard, "cut_run", cut_run)
    monkeypatch.setattr(agent_guard, "notify", lambda message, *, main: None)
    return cache, worktrees, cuts


def test_an_exhausted_verdict_on_one_slot_cuts_every_live_slot_of_the_backend(
    tmp_path, monkeypatch
):
    working = _assistant_event("2026-09-16T10:00:00Z")
    cache, worktrees, cuts = _two_live_claude_slots(
        tmp_path,
        monkeypatch,
        events_by_slot={1: [working], 2: [working, _rate_limit_event("rejected")]},
    )
    # The backend's verdict before this tick: allowed, as a previous tick left it.
    (cache / "agent_guard_claude.json").write_text(json.dumps({"last_quota_status": "allowed"}))

    results = [
        agent_guard._tick_backend(backend, main=tmp_path, slot=slot)
        for backend, slot in agent_guard.worker_slot_pairs()
    ]

    assert [result.cut_reason for result in results] == ["quota", "quota"]
    assert [result.backend for result in results] == ["claude", "claude-2"]
    assert cuts == [
        ("claude", "quota", 1, str(worktrees[1])),
        ("claude", "quota", 2, str(worktrees[2])),
    ]
    # One verdict per backend, shared by its slots -- and the change is reported once, not per slot.
    verdict = json.loads((cache / "agent_guard_claude.json").read_text())
    assert verdict["last_quota_status"] == "exhausted"
    assert [result.quota_changed for result in results] == [True, False]
    # Slot 2 keeps its stall bookkeeping in a file of its own.
    assert (cache / "agent_guard_claude-2.json").is_file()


def test_a_slot_that_sees_no_rate_limit_leaves_the_backend_allowed(tmp_path, monkeypatch):
    working = _assistant_event("2026-09-16T10:00:00Z")
    cache, _, cuts = _two_live_claude_slots(
        tmp_path, monkeypatch, events_by_slot={1: [working], 2: [working]}
    )
    results = [agent_guard._tick_backend("claude", main=tmp_path, slot=slot) for slot in (1, 2)]
    assert [result.cut_reason for result in results] == [None, None]
    assert cuts == []
    verdict = json.loads((cache / "agent_guard_claude.json").read_text())
    assert verdict["last_quota_status"] == "allowed"


def test_one_slot_keeps_every_path_the_backend_always_had(monkeypatch, tmp_path):
    monkeypatch.setenv("WORKER_CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("WORKER_WORKTREE", raising=False)
    paths = agent_guard.worker_paths("claude", tmp_path)
    assert paths.pidfile == tmp_path / "worker_claude.pid"
    assert paths.statefile == tmp_path / "worker_claude.state"
    assert paths.issuefile == tmp_path / "worker_claude.issue"
    assert paths.events == tmp_path / "worker_claude.jsonl"
    assert paths.bookkeeping == paths.quota_verdict == tmp_path / "agent_guard_claude.json"
    assert str(paths.worktree) == agent_guard.BACKEND_WORKTREES["claude"]
    # The example config declares no `slots:`, so every backend is its one slot.
    assert agent_guard.worker_slot_pairs() == [(name, 1) for name in agent_guard.BACKENDS]


def test_the_exit_hook_of_slot_two_ends_that_slot_and_names_it(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKER_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(
        agent_guard, "EXTRA_SLOT_WORKTREES", {("claude", 2): str(tmp_path / "example-claude-2")}
    )
    monkeypatch.setattr(agent_guard, "wake", lambda **kwargs: "woken")
    (tmp_path / "worker_claude.state").write_text("STARTED\n")
    (tmp_path / "worker_claude-2.state").write_text("STARTED\n")
    (tmp_path / "worker_claude-2.issue").write_text("348\n")

    assert agent_guard.check("claude", main=tmp_path, slot=2) == "claude-2: DONE"
    assert (tmp_path / "worker_claude-2.state").read_text().startswith("DONE")
    assert (tmp_path / "worker_claude.state").read_text() == "STARTED\n"
    [event] = agent_guard.pending_events(main=tmp_path)
    assert event.name.endswith("-worker_finished-claude-2")
    assert "claude-2 finished on its own on issue #348" in event.read_text()


def test_a_dirty_slot_holds_the_backend_back_only_when_no_other_slot_can_take_work(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("WORKER_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(
        agent_guard, "EXTRA_SLOT_WORKTREES", {("claude", 2): str(tmp_path / "example-claude-2")}
    )
    monkeypatch.setattr(agent_guard, "backend_worktree_present", lambda backend, slot=1: True)
    dirt = {1: [], 2: ["?? stray.py"]}
    monkeypatch.setattr(
        agent_guard,
        "backend_worktree_dirt",
        lambda backend, *, main, slot=1: list(dirt[slot]),
    )
    alive = {1: False, 2: False}
    monkeypatch.setattr(
        agent_guard,
        "_is_alive",
        lambda pidfile: alive[2 if pidfile.name == "worker_claude-2.pid" else 1],
    )
    # Slot 1 is idle and clean: the backend can take a dispatch, whatever slot 2 holds.
    assert agent_guard.backend_dispatch_dirt("claude", main=tmp_path) == []
    # Slot 1 busy, slot 2 idle and dirty: nothing free can take it -- that is dirt.
    alive[1] = True
    assert agent_guard.backend_dispatch_dirt("claude", main=tmp_path) == ["?? stray.py"]
    # Both busy: the cap's and the driver's business, not dirt.
    alive[2] = True
    assert agent_guard.backend_dispatch_dirt("claude", main=tmp_path) == []


# ---- the config key -----------------------------------------------------------------------------


def _slotted_project(**backends):
    return ProjectConfig(repo="owner/name", tracking_epic=1, board_number=1, backends=backends)


def test_slots_default_to_one_and_derive_the_other_slots_beside_the_first():
    project = _slotted_project(
        claude={"stream": "claude_jsonl", "worktree": "../host-claude", "slots": 3},
        qwen={"stream": "qwen_jsonl", "worktree": "../host-qwen"},
        reviewer={"stream": "claude_jsonl"},
    )
    assert project.backends["qwen"].slots == 1
    assert worker_slots(project) == [("claude", 1), ("claude", 2), ("claude", 3), ("qwen", 1)]
    assert [worker_slot_key("claude", n) for n in (1, 2, 3)] == ["claude", "claude-2", "claude-3"]
    assert [worker_slot_worktree(project.backends["claude"], n) for n in (1, 2, 3)] == [
        "../host-claude",
        "../host-claude-2",
        "../host-claude-3",
    ]


@pytest.mark.parametrize(
    ("backends", "message"),
    [
        ({"claude": {"stream": "claude_jsonl", "worktree": "../c", "slots": 0}}, "at least 1"),
        ({"claude": {"stream": "claude_jsonl", "slots": 2}}, "needs a worktree"),
        (
            {
                "claude": {"stream": "claude_jsonl", "worktree": "../c", "slots": 2},
                "claude-2": {"stream": "claude_jsonl", "worktree": "../other"},
            },
            "worker_claude-2",
        ),
        (
            {
                "claude": {"stream": "claude_jsonl", "worktree": "../c", "slots": 2},
                "qwen": {"stream": "qwen_jsonl", "worktree": "../c-2"},
            },
            "would share the worktree",
        ),
    ],
)
def test_a_slot_that_could_clobber_another_fails_at_config_load(backends, message):
    with pytest.raises(ValidationError, match=message):
        _slotted_project(**backends)


def test_the_doctor_checks_every_slots_worktree(tmp_path):
    project = _slotted_project(
        claude={"stream": "claude_jsonl", "worktree": "host-claude", "slots": 2},
    )
    (tmp_path / "host-claude" / ".git").mkdir(parents=True)
    check = doctor.check_worktrees(project, tmp_path)
    assert not check.ok
    assert "claude-2" in check.detail
    (tmp_path / "host-claude-2" / ".git").mkdir(parents=True)
    assert doctor.check_worktrees(project, tmp_path).ok


def test_the_driver_lists_a_backends_slots_through_the_library(tmp_path):
    environment, _, worktrees = _slotted_environment(tmp_path, labels_by_issue={})
    listed = subprocess.run(
        [sys.executable, "-m", "agent_os.lib", "worker-slots", "claude"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    assert listed == [
        f"claude\t1\tclaude\t{worktrees[0]}",
        f"claude\t2\tclaude-2\t{worktrees[1]}",
    ]


def test_a_chained_run_on_slot_two_stays_on_slot_two_to_its_exit_hook(tmp_path):
    """The run's own subshell carries its slot: `stage-exit`, the next stage's `launch-stage`,
    `open-pr` and the guard's exit hook all act on slot 2's files, and slot 1's are never written.
    """
    environment, cache, worktree, _ = _staged_environment(
        tmp_path, stage_titles=("Write the failing test", "Make it pass"), mode="stage_commit"
    )
    environment["AGENTS_CONFIG_PATH"] = str(
        _config_with_claude_slots(
            tmp_path, slots=2, max_parallel_issues=2, worktree=tmp_path / "configured-claude"
        )
    )
    try:
        with _planner_lock_held(cache):
            started = _driver(environment, "start", "347", "--slot", "2")
            assert started.returncode == 0, started.stdout + started.stderr
            assert _wait_until(lambda: _events_of_kind(cache, "worker_finished")), (
                cache / "worker_claude-2.log"
            ).read_text()
            [finished] = _events_of_kind(cache, "worker_finished")
            assert finished.name.endswith("-worker_finished-claude-2")
            assert (cache / "worker_claude-2.stage").read_text().strip() == "2/2"
            assert (cache / "worker_claude-2.state").read_text().startswith("DONE")
            assert _subjects(worktree)[:2] == [
                "stage 2/2: Make it pass",
                "stage 1/2: Write the failing test",
            ]
            assert not [name for name in _cache_files(cache) if name.startswith("worker_claude.")]
    finally:
        _driver(environment, "stop", "--slot", "2")
