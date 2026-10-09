"""A puntal and a worker never limit each other: the puntal's code and its driver do not read the
worker cap (`planner.max_parallel_issues`) or any backend's `slots`, so what builds the unblocked
parts of a product and what serves its actions run at once, sharing only the account's quota
(docs/tree/fr-independent-work-runs-in-parallel.md, docs/tree/dec-puntales-run-as-headless-processes.md).

Pure filesystem. This file must not request the `engine` or `db_sandbox` fixture.
"""

from __future__ import annotations

import re

from agent_os.cli import AGENT_OS_DIR

WORKER_CAP_WORDS = re.compile(r"max_parallel_issues|worker[_-]slots|backend_slots|\bslots?\b")
PUNTAL_FILES = [
    *sorted((AGENT_OS_DIR / "agent_os" / "product" / "puntal").rglob("*.py")),
    AGENT_OS_DIR / "bin" / "puntal_task.sh",
]


def test_the_puntal_driver_and_its_code_exist_to_be_checked():
    assert len(PUNTAL_FILES) > 5
    assert all(path.is_file() for path in PUNTAL_FILES)


def test_no_puntal_file_reads_the_worker_cap_or_the_slots():
    offenders = {
        path.relative_to(AGENT_OS_DIR).as_posix(): WORKER_CAP_WORDS.findall(path.read_text())
        for path in PUNTAL_FILES
        if WORKER_CAP_WORDS.search(path.read_text())
    }
    assert offenders == {}
