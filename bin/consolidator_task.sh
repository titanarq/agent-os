#!/usr/bin/env bash
# Drives the CONSOLIDATOR: for one open `consolidate.<node>` job issue (raised by test-session ingestion
# when an amendment contradicts or qualifies a use case), one headless turn with no tool drafts the
# use case again as ONE definition, a second turn on a stronger class reviews the draft, and only an
# approved draft becomes a pull request that `Closes` the issue. A rejected draft is never opened: the
# issue gets a comment with the reasons and stays open.
#
#   agent_os/bin/consolidator_task.sh <issue>
#
# Exit status: 0 the pull request is open, 2 not run, 3 no valid draft or review, 4 the reviewer
# rejected the draft. STDOUT is the pull request's URL or the reason; stderr carries diagnostics.
#
# Its classes are `consolidator` (drafts) and `consolidation-reviewer` (reviews) in
# `config/agents.yaml`. **Writes**: `.cache/consolidator/<ts>-<role>.log` (+ `.exited`);
# `AGENT_CACHE_DIR` moves it. `<ROLE>_<BACKEND>_BIN` (for example `CONSOLIDATOR_CLAUDE_BIN`) names the
# backend binary, for a test.
set -uo pipefail

# shellcheck source=agent_os/bin/_python.sh
source "$(dirname "${BASH_SOURCE[0]}")/_python.sh"
agent_main=$(agent_os_host_root)
cd "$agent_main" || exit 2
agent_python=$(agent_os_python)
export AGENT_OS_HOST_ROOT=$agent_main AGENT_OS_PYTHON=$agent_python AGENT_OS_DIR=$agent_os_dir

exec "$agent_python" -m agent_os.product.session_ingest.consolidation "$@"
