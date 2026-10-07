"""The executor's contract: the app's code applies a validated plan atomically and reports back as
JSON; agent-os runs it, reads its verdict and never applies anything itself.

The reference executor (`agent_os.product.puntal.fast.reference_executor`) is shown against an
in-memory store, then the bench's file-backed one is driven through the same interface.

Pure filesystem and subprocess. This file must not request the `engine` or `db_sandbox` fixture.
"""

from __future__ import annotations

import json
import pathlib
import sys

import pytest

from agent_os.cli import AGENT_OS_DIR
from agent_os.product.puntal.fast.executor import ExecutorVerdict, run_executor
from agent_os.product.puntal.fast.reference_executor import apply_operations

BENCH_EXECUTOR = AGENT_OS_DIR / "bench" / "puntal" / "executor.py"


class MemoryStore:
    """The smallest app that can be an executor's target."""

    def __init__(self):
        self.documents: dict[tuple[str, str], dict] = {}
        self.counters: dict[str, int] = {}
        self.committed = 0

    def exists(self, collection, identifier):
        return (collection, identifier) in self.documents

    def put(self, collection, identifier, document):
        self.documents[(collection, identifier)] = document

    def update(self, collection, identifier, changes):
        self.documents[(collection, identifier)].update(changes)

    def delete(self, collection, identifier):
        del self.documents[(collection, identifier)]

    def next_number(self, counter):
        self.counters[counter] = self.counters.get(counter, 0) + 1
        return self.counters[counter]

    def transaction(self):
        import contextlib

        @contextlib.contextmanager
        def scope():
            yield
            self.committed += 1

        return scope()


def test_the_reference_executor_applies_in_order_and_hands_back_what_it_allocated():
    store = MemoryStore()
    verdict = apply_operations(
        store,
        [
            {"op": "allocate", "counter": "ticket", "bind": "n"},
            {"op": "put", "collection": "tickets", "id": "T-{{n}}", "document": {"id": "T-{{n}}"}},
        ],
    )
    assert verdict == {"ok": True, "bindings": {"n": 1}}
    assert store.documents == {("tickets", "T-1"): {"id": "T-1"}} and store.committed == 1


def test_a_plan_the_app_cannot_apply_changes_nothing_and_says_why():
    store = MemoryStore()
    store.put("tickets", "T-1", {"status": "open"})
    verdict = apply_operations(
        store,
        [
            {"op": "update", "collection": "tickets", "id": "T-1", "changes": {"status": "x"}},
            {"op": "delete", "collection": "tickets", "id": "T-9"},
        ],
    )
    assert verdict["ok"] is False and "tickets/T-9" in verdict["errors"][0]
    assert store.documents[("tickets", "T-1")] == {"status": "open"}
    assert store.counters == {}


def write_executor(tmp_path: pathlib.Path, body: str) -> list[str]:
    script = tmp_path / "executor.py"
    script.write_text(body)
    return [sys.executable, str(script)]


def test_the_executor_is_handed_the_operations_on_stdin_and_its_verdict_is_read_from_stdout(
    tmp_path,
):
    command = write_executor(
        tmp_path,
        "import json, sys\n"
        "plan = json.load(sys.stdin)\n"
        "print(json.dumps({'ok': True, 'bindings': {'seen': len(plan['operations'])}}))\n",
    )
    verdict = run_executor(
        command, [{"op": "delete", "collection": "c", "id": "i"}], timeout_seconds=30
    )
    assert verdict == ExecutorVerdict(ok=True, bindings={"seen": 1}, errors=[], crashed=False)


def test_a_refusal_is_a_verdict_and_can_be_retried_but_a_crash_is_not():
    refusal = run_executor(
        [
            sys.executable,
            "-c",
            "import json; print(json.dumps({'ok': False, 'errors': ['no T-9']}))",
        ],
        [],
        timeout_seconds=30,
    )
    assert (refusal.ok, refusal.errors, refusal.crashed) == (False, ["no T-9"], False)
    for broken in (
        [sys.executable, "-c", "import sys; sys.exit(3)"],
        [sys.executable, "-c", "print('not json')"],
        [sys.executable, "-c", "print('[]')"],
        [sys.executable, "-c", 'print(\'{"ok": "yes"}\')'],
        ["/nonexistent/executor"],
    ):
        verdict = run_executor(broken, [], timeout_seconds=30)
        assert verdict.crashed and not verdict.ok and verdict.errors, broken


def test_an_executor_that_hangs_is_cut_at_the_timeout():
    verdict = run_executor(
        [sys.executable, "-c", "import time; time.sleep(60)"], [], timeout_seconds=1
    )
    assert verdict.crashed and "1s" in verdict.errors[0]


@pytest.fixture
def bench_store(tmp_path):
    return tmp_path / "store"


def test_the_bench_executor_applies_a_plan_to_the_file_store_and_keeps_the_derived_summary(
    bench_store,
):
    command = [sys.executable, str(BENCH_EXECUTOR), "--dir", str(bench_store)]
    verdict = run_executor(
        command,
        [
            {"op": "allocate", "counter": "ticket", "bind": "n"},
            {
                "op": "put",
                "collection": "tickets",
                "id": "T-{{n}}",
                "document": {
                    "id": "T-{{n}}",
                    "title": "x",
                    "priority": "normal",
                    "status": "open",
                    "resolution": None,
                },
            },
        ],
        timeout_seconds=30,
    )
    assert verdict.ok and verdict.bindings == {"n": 1}
    stored = json.loads((bench_store / "tickets" / "T-1.json").read_text())
    assert stored["status"] == "open"
    # The summary is the APP's derived data: the puntal never wrote it.
    summary = json.loads((bench_store / "summary" / "board.json").read_text())
    assert summary == {"open": 1, "in_progress": 0, "resolved": 0, "total": 1}


def test_the_bench_executor_refuses_a_whole_plan_when_one_operation_cannot_apply(bench_store):
    command = [sys.executable, str(BENCH_EXECUTOR), "--dir", str(bench_store)]
    verdict = run_executor(
        command,
        [
            {"op": "allocate", "counter": "ticket", "bind": "n"},
            {"op": "update", "collection": "tickets", "id": "T-404", "changes": {"status": "x"}},
        ],
        timeout_seconds=30,
    )
    assert not verdict.ok and not verdict.crashed and "T-404" in verdict.errors[0]
    assert not (bench_store / "_counters.json").exists()
