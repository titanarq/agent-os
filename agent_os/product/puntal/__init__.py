"""The puntal driver's Python half (Agentos v2): one UI action answered live by one headless agent
process, planned in ONE model turn, executed by code, and measured.

A PUNTAL is the shore that props a building up: the product's interface goes live early, every action
is bound to a use case, and an action nobody has implemented yet is answered by this process instead
of by code (`docs/AGENTOS_V2_PLAN.md`). The shell entry is `bin/puntal_task.sh`, a sibling of
`worker_task.sh` that does nothing but start this package under the mechanism's own interpreter, so a
click pays for one Python start-up and not for a chain of `python -m agent_os.lib ...` calls.

THE CONTRACT (`docs/tree/dec-a-puntal-plans-in-one-turn-and-code-executes.md`), by sub-package:

- `fast/`       pre-helper (`pre_helper.py`: loads the state the node declares it reads), the brief,
                the plan's JSON shape and its validation (`operations.py`), and the executor
                interface (`executor.py`) with a reference implementation (`reference_executor.py`).
- `stream/`     the backend: confining flags, the `./state` shim, the process, the audit of every
                tool call and the observer that folds the stream as it arrives.
- `telemetry/`  the record (`TELEMETRY_SCHEMA`), the `runs.tsv` row, the post-helpers and the owner's
                feedback.
- `invocation.py` ties them: pre-helper, plan turn, executor, at most one retry and one slow turn.
- `json_api.py` the generic API for a host's shell; `cli.py` the command line.

HOW "THE PUNTAL NEVER WRITES CODE" IS ENFORCED -- as far as the `claude` CLI allows, in layers:

0. On the fast path the model has NO tool at all (`--tools=`): it returns text, and what changes
   state is the app's executor applying operations agent-os validated. Any tool call on that path
   is a contract violation and cuts the run.
1. On the slow path, `--tools Bash`: every other built-in tool (Write, Edit, Read, WebFetch, Task...)
   is not in the model's context at all. `--safe-mode` keeps the user's CLAUDE.md, skills, plugins,
   hooks and MCP servers out of it as well, which is also what keeps the context floor small.
2. `--permission-mode dontAsk` with ONE allow rule, `Bash(./state *)`: a call that would ask for
   approval is denied, so the only Bash command that runs is the persistence shim this driver wrote
   into the run's empty scratch directory. The CLI auto-approves read-only commands (`cat`, `ls`)
   whatever the rules say, which is why layers 3 and 4 exist.
3. The stream audit: every `tool_use` is checked as it is assembled, before its result can return
   (`audit_tool_call`): it must be Bash, run `./state`, and carry no shell operator or command
   substitution. The first violation kills the run's process group and the run ends as
   `contract_violation`.
4. The record: every tool call, every violation, every file left in the scratch directory and the
   CLI's own permission denials are written to the telemetry, so "the puntal wrote no code" is a
   query over the log and not a belief.
"""

from agent_os.product.puntal.cli import main
from agent_os.product.puntal.constants import (
    EXIT_ANSWERED,
    EXIT_BACKEND_FAILED,
    EXIT_CEILING_CUT,
    EXIT_CONTRACT_VIOLATION,
    EXIT_EXECUTOR_FAILED,
    EXIT_INVALID_PLAN,
    EXIT_NOT_RUN,
    EXIT_TIMEOUT,
    OUTCOME_EXIT_STATUS,
    PuntalRefused,
)
from agent_os.product.puntal.stream.audit import audit_tool_call, split_gap_note
from agent_os.product.puntal.stream.events import Ceilings
from agent_os.product.puntal.stream.launch import (
    backend_executable_for,
    backend_flags,
    write_state_shim,
)
from agent_os.product.puntal.stream.observer import StreamObserver
from agent_os.product.puntal.telemetry.record import TELEMETRY_FIELDS, TELEMETRY_SCHEMA

__all__ = [
    "EXIT_ANSWERED",
    "EXIT_BACKEND_FAILED",
    "EXIT_CEILING_CUT",
    "EXIT_CONTRACT_VIOLATION",
    "EXIT_EXECUTOR_FAILED",
    "EXIT_INVALID_PLAN",
    "EXIT_NOT_RUN",
    "EXIT_TIMEOUT",
    "OUTCOME_EXIT_STATUS",
    "TELEMETRY_FIELDS",
    "TELEMETRY_SCHEMA",
    "Ceilings",
    "PuntalRefused",
    "StreamObserver",
    "audit_tool_call",
    "backend_executable_for",
    "backend_flags",
    "main",
    "split_gap_note",
    "write_state_shim",
]
