#!/usr/bin/env bash
# Drives the integrator's ONE MODEL STEP: one headless agent turn with no tool reads an index of the
# group of ready pull requests the script allowed and answers, as JSON, whether they are independent
# (`independent`, `unsure` or `coupled`, a reason each). It may only confirm, split or send solo. It is
# the interpreter's sibling and shares the puntal's turn runner. `agent-os-integrate plan --judge`
# runs the same judgment in-process.
#
#   agent_os/bin/integrator_task.sh judge [--request FILE|-] [--model M] [--dry-run]
#
# STDIN (or --request) is the index JSON; STDOUT is ONE JSON object whatever happened, with every pull
# request alone when no judgment could be had; stderr carries the diagnostics. Exit status: 0 judged,
# 1 the backend failed, 2 not run, 3 contract violation, 4 ceiling cut, 5 invalid answer, 124 timeout.
#
# Its class is `integrator` in `config/agents.yaml`. **Writes**: `.cache/integrator/<ts>.log` (+
# `.exited`); `AGENT_CACHE_DIR` moves it. `INTEGRATOR_<BACKEND>_BIN` names the backend binary, for a test.
set -uo pipefail

# shellcheck source=agent_os/bin/_python.sh
source "$(dirname "${BASH_SOURCE[0]}")/_python.sh"
agent_main=$(agent_os_host_root)
cd "$agent_main" || exit 2
agent_python=$(agent_os_python)
export AGENT_OS_HOST_ROOT=$agent_main AGENT_OS_PYTHON=$agent_python AGENT_OS_DIR=$agent_os_dir

exec "$agent_python" -m agent_os.product.integrator.judge "$@"
