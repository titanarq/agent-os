"""The names, exit statuses and paths the whole puntal package shares."""

from __future__ import annotations

import pathlib

# `agent_os/product/puntal/constants.py` -> the directory `bootstrap.sh` builds a virtualenv beside (what
# `agent_os.cli.AGENT_OS_DIR` is, without importing the CLI on the click's critical path).
AGENT_OS_DIR = pathlib.Path(__file__).resolve().parents[3]

PUNTAL_ROLE = "puntal"
# The slow path's contract is a prompt of its own: the same role, a different job.
SLOW_PATH_PROMPT = "puntal_slow"

# The one command the slow path's puntal may run, and the name of the shim the driver writes for it
# in the run's empty scratch directory. Short and relative on purpose: the model types it on every call.
STATE_COMMAND = "./state"
SHIM_NAME = "state"
PERSISTENCE_TOOL = "Bash"
# The CLI's permission rule for exactly that command and its arguments.
ALLOW_RULE = f"{PERSISTENCE_TOOL}({STATE_COMMAND} *)"

# What introduces the app's data API in the FAST contract, whose turn has no tool: the text the host
# configured (`puntal.persistence_api_file`) describes commands, and the fast turn must not take them
# for something it can run. Part of the mechanism and not of the prompt template, so that a host
# that documents no API gets no heading with nothing under it.
FAST_PATH_API_INTRODUCTION = (
    "THE APP'S DATA API\n"
    "Reference only: you have no tool in this turn and run none of these commands. It tells you what "
    "the app stores and how, so that the operations you send are ones its code can apply.\n\n"
)

# The environment variable through which the app's own commands (the pre-helper's reads, the
# executor, the slow path's `./state`) learn who is acting (`fast/actor.py`, docs/AGENT_OS.md 4.7).
ACTOR_VARIABLE = "PUNTAL_ACTOR"

# The line that ends a slow-path response which asked for something its node does not describe.
GAP_MARKER = "GAP:"

# The stream dialect this driver can confine: the flags below are the `claude` CLI's.
SUPPORTED_STREAM = "claude_jsonl"

# Nonessential egress (version checks, telemetry) is start-up latency the person waiting on a click
# should not pay for.
BACKEND_ENVIRONMENT = {"CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"}

PATH_FAST = "fast"
PATH_SLOW = "slow"

EXIT_ANSWERED = 0
EXIT_BACKEND_FAILED = 1
EXIT_NOT_RUN = 2
EXIT_CONTRACT_VIOLATION = 3
EXIT_CEILING_CUT = 4
EXIT_INVALID_PLAN = 5
EXIT_EXECUTOR_FAILED = 6
EXIT_TIMEOUT = 124

OUTCOME_EXIT_STATUS = {
    "ok": EXIT_ANSWERED,
    "error": EXIT_BACKEND_FAILED,
    "contract_violation": EXIT_CONTRACT_VIOLATION,
    "ceiling_cut": EXIT_CEILING_CUT,
    "invalid_plan": EXIT_INVALID_PLAN,
    "executor_failed": EXIT_EXECUTOR_FAILED,
    "timeout": EXIT_TIMEOUT,
}

# How long a run that was told to stop gets to leave before it is killed outright.
TERMINATION_GRACE_SECONDS = 3.0
STDERR_TAIL_LINES = 20

# The most model turns one invocation may take: the plan, then ONE more -- either a retry after a
# rejected plan or the slow path's read of state the node did not declare -- and, after the slow
# path, nothing: it answers for itself.
MAX_RETRIES = 1


class PuntalRefused(Exception):
    """A puntal that cannot be run as configured. Raised before anything is spent or written."""
