#!/usr/bin/env bash
# Drives ONE INTERPRETATION of the owner's chat message in a test session (Agentos v2): one headless
# agent turn with no tool reads the thread, the message and the case, and answers as JSON (a short
# reply, and the items it understood). It is a puntal's sibling and shares its turn runner; the
# contract -- request, envelope, errors -- is docs/FEEDBACK_INTERPRETER.md.
#
#   agent_os/bin/interpreter_task.sh interpret [--request FILE|-] [--tree-root DIR] [--model M]
#       [--timeout SECONDS] [--telemetry-file F] [--dry-run]
#
# STDIN (or --request) is the request JSON; STDOUT is ONE JSON envelope whatever happened; stderr
# carries the diagnostics. Exit status: 0 interpreted, 1 the backend failed, 2 not run, 3 contract
# violation, 4 ceiling cut, 5 invalid answer after its retry, 124 safety timeout.
#
# Its class is `interpreter` in `config/agents.yaml` and its settings the `interpreter:` section.
# **Writes**: `.cache/interpreter/<ts>.log` (+ `.exited`), `runs.tsv` and `telemetry.jsonl` there;
# `AGENT_CACHE_DIR` moves them. `INTERPRETER_<BACKEND>_BIN` names the backend binary, for a test.
set -uo pipefail

# shellcheck source=agent_os/bin/_python.sh
source "$(dirname "${BASH_SOURCE[0]}")/_python.sh"
agent_main=$(agent_os_host_root)
cd "$agent_main" || exit 2
agent_python=$(agent_os_python)
export AGENT_OS_HOST_ROOT=$agent_main AGENT_OS_PYTHON=$agent_python AGENT_OS_DIR=$agent_os_dir

exec "$agent_python" -m agent_os.product.interpreter "$@"
