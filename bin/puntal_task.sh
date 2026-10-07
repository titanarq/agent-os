#!/usr/bin/env bash
# Drives ONE PUNTAL (Agentos v2): the live stand-in for one UI action that has no hand-written
# implementation yet. A person clicked; the node's declared reads are loaded by code, one headless
# agent turn with NO tool plans the answer as JSON (operations and answer), and the app's executor
# applies the operations. A plan that needs undeclared state costs one slow turn, the confined tool
# loop. Never a worker: it holds no worktree, writes no code and cannot (the layers are in
# agent_os/product/puntal/__init__.py's docstring), and nothing it does reaches the tracker or the
# planner. The contract is docs/tree/dec-a-puntal-plans-in-one-turn-and-code-executes.md.
#
#   agent_os/bin/puntal_task.sh --action ACTION --node-file NODE.md [--payload TEXT | --payload-file F]
#       [--state-file F] [--read 'CMD' ...] [--node-id ID] [--session-id S] [--invocation-id ID]
#       [--label KEY=VALUE ...] [--path fast|slow] [--model M] [--effort E] [--timeout SECONDS]
#       [--persistence-command CMD] [--executor-command CMD] [--telemetry-file F] [--dry-run]
#   agent_os/bin/puntal_task.sh --json [--plan-only]     # the shell API: JSON request in, envelope out
#   agent_os/bin/puntal_task.sh feedback --invocation-id ID --verdict accept|reject|retry [--note T]
#
# STDOUT is the response and nothing else (the node slice, the payload and the state are plain text,
# from a file or from stdin with `-`); stderr carries the diagnostics. Exit status: 0 answered, 1 the
# backend failed, 2 not run (refused before anything was spent), 3 the run broke the contract, 4 a
# ceiling cut it, 5 the plan was invalid after its retry, 6 the executor failed, 124 the safety
# timeout killed it. `--dry-run` prints the launch and spends nothing.
#
# Its class is `puntal` in `config/agents.yaml` (`classes.puntal`, its model and its per-invocation
# ceilings) and its settings are the `puntal:` section; the persistence command is
# `puntal.persistence_command`, or `PUNTAL_PERSISTENCE_COMMAND`, or `--persistence-command`, and the
# executor command is `puntal.executor_command`, `PUNTAL_EXECUTOR_COMMAND` or `--executor-command`.
#
# **Writes**: one log per run, `.cache/puntal/<utc-timestamp>-<microseconds>-<pid>.log` (never
# truncated, never reused) with its `.exited` marker, one `.cache/puntal/runs.tsv` row (ts, context,
# model, turns, cost -- the columns of every role's), one JSON line in the telemetry file
# (`.cache/puntal/telemetry.jsonl`, or `--telemetry-file`) whose shape is documented in
# agent_os/docs/AGENT_OS.md §4.7, and, for `feedback`, `.cache/puntal/feedback.jsonl`. The last three
# are written AFTER the response has been handed over. `AGENT_CACHE_DIR` moves them, as it does for
# the validator and the refiner. `PUNTAL_<BACKEND>_BIN` names the backend binary, for a test or a
# bench that stands a stub in for it.
#
# Unlike the other role drivers it does not detach, does not wake the planner and mints no GitHub
# identity: the caller is waiting for the answer on stdout.
set -uo pipefail

# The epoch second of THIS moment, so every latency the telemetry records is measured from the
# click's arrival here and includes the interpreter's own start-up.
PUNTAL_LAUNCH_EPOCH=$(date +%s.%N)
export PUNTAL_LAUNCH_EPOCH

# shellcheck source=agent_os/bin/_python.sh
source "$(dirname "${BASH_SOURCE[0]}")/_python.sh"
agent_main=$(agent_os_host_root)
cd "$agent_main" || exit 2
agent_python=$(agent_os_python)
export AGENT_OS_HOST_ROOT=$agent_main AGENT_OS_PYTHON=$agent_python AGENT_OS_DIR=$agent_os_dir

exec "$agent_python" -m agent_os.product.puntal "$@"
