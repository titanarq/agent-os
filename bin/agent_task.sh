#!/usr/bin/env bash
# Drives ONE-SHOT headless roles -- the ones that read, judge and exit, never the ones that hold a
# worktree. Today that is the VALIDATOR (reviews a pull request against its issue's acceptance
# criteria) and the REFINER (turns a raw issue into template-conformant sub-issues with a budget
# class, or rewrites a small task/bug's body in place;
# docs/adr/2026-09-15-the-refiner-runs-unattended-only-after-a-human-reviewed-its-dry-run.md).
#
#   agent_os/bin/agent_task.sh <role> <issue|pr> [context...] [--dry-run] [--no-wake]
#
# `<role>` is resolved against `config/agents.yaml`: the one class carrying `role: <role>` names
# the model and the ceiling, and `project.role_apps` (falling back to `project.planner_app`) names
# the GitHub App it signs as -- the validator must not be the PR's own author
# (docs/adr/2026-09-14-a-pr-is-validated-by-a-validator-agent-against-the-issues-acceptance-
# criteria.md). Nothing here is a literal of one project
# (docs/adr/2026-09-14-the-agent-mechanism-is-project-agnostic-and-configured-not-coded.md).
#
# WHICH BACKEND RUNS IT is a second decision, made after that one and by the launch gate (#425):
# the class names the backend, and a class that also declares a `fallback:` runs on it when the
# guard's own persisted verdict says the class's backend is out of quota. The verdict is read off
# `.cache/agent_guard_<backend>.json` and never claimed by an agent
# (docs/adr/2026-09-14-quota-exhaustion-is-read-from-the-backend-not-claimed-by-the-agent.md), and
# one older than `mechanism.quota_verdict_ttl_minutes` reads as unknown, which launches the class's
# own backend. A substituted run names itself everywhere the mechanism reads: the identity lines
# below and in the log header, the `runs.tsv` row's model, the `<role>_finished` event, and -- for
# the validator -- the first line of the review it posts.
#
# A one-shot role runs in the MAIN CHECKOUT and never holds a worktree of its own. A role that runs
# tests gets a throwaway one under `.cache/`, made and removed by this driver, exported to the
# backend as `PYTHONPATH` and named by its own path in that role's RULES -- the `__WORKTREE__`
# placeholder -- so the agent runs in what the driver prepared and never builds an environment of
# its own (`agent_prepare_worktree`; `AGENT_WORKTREE_REF` names the ref for a run against a stub
# backend instead of the pull request's own head).
#
# **Writes**: one log per run, `.cache/<role>/<utc-timestamp>.log` (never truncated, never
# reused), the run's own PID beside it as `.cache/<role>/<utc-timestamp>.pid`, one appended line in
# `.cache/<role>/runs.tsv` (ts, context, model, turns, cost), and at the end one planner event
# `<role>_finished-<subject>` followed by `agent_guard.py wake` -- the same two steps the worker's
# exit hook takes. `AGENT_CACHE_DIR` moves all four plus that worktree, for a dry run against a
# stub backend. `--dry-run` prints the resolved model, identity and prompt and exits without
# calling the backend at all (and without minting a token). `--no-wake` is for a manual run a human
# wants to review before the planner acts on it: the log and runs.tsv are written as usual, but
# neither the `<role>_finished` event nor `wake` is called.
#
# **The launch is detached** (#400): the driver prepares the run, hands it to `setsid` and returns
# at once, printing the run's PID, its PID file and its log. The run then finishes whatever the
# process that launched the driver does next -- a planner whose own turn ends takes its whole
# process group down with it, and that is how PR #399 was left with no review and with nothing
# recording that the review never happened. The PID file lives exactly as long as the run is
# unfinished: the run removes it when it reaches its own end, so a PID that is dead beside a log
# holding no `result` event is a run that died, and that is what the guard reports.
#
# This file is also SOURCED by agent_os/bin/planner_task.sh for the four helpers below, so the identity
# block, the per-run log and the runs.tsv row have one implementation across every role.
set -uo pipefail

# The package's own interpreter and the HOST project's root, resolved in ONE place for every driver
# in this directory and EXPORTED, so a child process -- a worker's subshell, the guard's exit hook,
# a launch that re-enters this file detached -- is handed both answers instead of resolving them
# again from whatever tree it happens to stand in.
# shellcheck source=agent_os/bin/_python.sh
source "$(dirname "${BASH_SOURCE[0]}")/_python.sh"
agent_main=$(agent_os_host_root)
cd "$agent_main"
agent_python=$(agent_os_python)
export AGENT_OS_HOST_ROOT=$agent_main
export AGENT_OS_PYTHON=$agent_python
export AGENT_OS_DIR=$agent_os_dir

agent_project_value() { "$agent_python" -m agent_os.lib project-value "$@"; }

# The backend CLI a driver launches, from `project.executables` rather than from whatever PATH the
# process that launched the driver happened to carry -- the same resolver every driver uses, keyed
# by command name, so an unattended dispatch and a shell dispatch resolve the same binary (#380).
# A name the project does not configure comes back unchanged, which is the bare-name PATH lookup
# these drivers already did. `$2`, when given, is the caller's own environment override and wins
# without asking the config anything.
#
# RETURNS NON-ZERO, AND EVERY CALLER MUST STOP ON IT. A `config/agents.yaml` that does not load
# makes the resolver exit 1 with an empty stdout, and `${VAR:-$(...)}` would swallow that into an
# empty command: the driver would then run `"" --model ...`, the shell would answer 127, and the
# failed-launch report would name an empty executable -- pointing whoever is debugging at the very
# key the broken file made unreadable. A broken config is a loud stop, never a fallback.
agent_executable() {
  local name=$1 override=${2:-} resolved
  if [ -n "$override" ]; then printf '%s\n' "$override"; return 0; fi
  resolved=$("$agent_python" -m agent_os.lib backend-executable "$name") || return 1
  [ -n "$resolved" ] || { echo "agent_lib backend-executable $name printed nothing" >&2; return 1; }
  printf '%s\n' "$resolved"
}

# The one class carrying `role: <role>`: `--field name` is its name, anything else is a field of
# the class (model, backend, max_context...). Exits non-zero, with the reason on stderr, when no
# class -- or more than one -- claims the role.
agent_role_field() {
  "$agent_python" -m agent_os.lib role-class "$1" --field "${2:-model}"
}

# THE LAUNCH GATE (#425): which backend a role's run actually gets, read off the guard's OWN
# persisted quota verdict (`.cache/agent_guard_<backend>.json`, `last_quota_status`) and never off
# an agent's claim about its own quota -- the role has not run yet, so there is no stream of its own
# to read, and the one authority on Claude's window at that moment is what the guard last saw.
# `exhausted` inside `mechanism.quota_verdict_ttl_minutes` with a fallback declared on the class
# launches the fallback; `allowed`, unknown, stale, or exhausted with nothing declared launches the
# class's own backend, exactly as before the gate existed.
#
# Sets five globals the rest of the driver uses -- launch_backend, model, launch_substituted,
# launch_ceilings and launch_reason -- and RETURNS NON-ZERO on an answer it cannot use, so a broken
# config stops the launch instead of becoming an empty command line the shell answers 127 with
# (the same rule `agent_executable` above holds, #380). Lives above the sourcing guard because
# planner_task.sh launches a role too and the decision has one implementation.
agent_read_launch_gate() {
  local role=$1 line
  line=$("$agent_python" -m agent_os.lib role-backend "$role") || return 1
  IFS=$'\t' read -r launch_backend model launch_substituted launch_ceilings launch_reason <<<"$line"
  if [ -z "$launch_backend" ] || [ -z "$model" ]; then
    echo "agent_lib role-backend $role printed no backend or no model: '$line'" >&2
    return 1
  fi
  return 0
}

# The one identity line that says which backend is about to run, for stdout and for the log header
# alike: a substituted run names itself wherever the mechanism reads it, so spend accounting never
# books Qwen tokens to a Claude class (`docs/AGENT_OS.md` §3, `.claude/agents/control-plane.md`
# Duty 5, which reports Claude in USD and Qwen in tokens). `$1` is the class's own backend, the one
# the substitution is a substitution FOR.
agent_backend_identity_line() {
  local own_backend=$1
  if [ "$launch_substituted" = yes ]; then
    echo "backend:   $launch_backend (FALLBACK for $own_backend -- $launch_reason)"
  else
    echo "backend:   $launch_backend"
  fi
}

# The flags that differ between the two backends, into the one array every launch expands: qwen
# takes `-o stream-json` and `--approval-mode yolo`, claude takes `-p`, `--output-format
# stream-json --verbose` and `--dangerously-skip-permissions`. The SAME two shapes
# `worker_task.sh`'s launch case uses -- an array so that the model, the rules and the instruction
# a role is handed keep one implementation instead of one per backend.
agent_backend_flags=()
agent_set_backend_flags() {
  case "$1" in
    qwen) agent_backend_flags=(--approval-mode yolo -o stream-json) ;;
    *)
      agent_backend_flags=(
        -p --output-format stream-json --verbose --dangerously-skip-permissions
      )
      ;;
  esac
}

# Mints the role's GitHub App token and exports it plus the bot's git author/committer, so every
# comment, review and label the run makes is attributable to that App and never to the human
# account. Missing or unusable secrets degrade to ONE warning and the ambient gh/git identity --
# never a hard failure, the same way worker_task.sh and planner_task.sh already degrade.
agent_apply_identity() {
  local slug=$1 secrets_dir bot_name bot_email
  secrets_dir=$(agent_project_value --path secrets_dir) || secrets_dir=""
  if [ -n "$slug" ] && [ -f "$secrets_dir/$slug.json" ]; then
    if GH_TOKEN=$("$agent_python" -m agent_os.gh_app_token --app "$slug") \
       && bot_name=$("$agent_python" -m agent_os.gh_app_token --app "$slug" --bot-name) \
       && bot_email=$("$agent_python" -m agent_os.gh_app_token --app "$slug" --bot-email); then
      export GH_TOKEN GIT_AUTHOR_NAME="$bot_name" GIT_COMMITTER_NAME="$bot_name"
      export GIT_AUTHOR_EMAIL="$bot_email" GIT_COMMITTER_EMAIL="$bot_email"
      echo "identity:  $bot_name <$bot_email>"
      return 0
    fi
    echo "WARNING: $slug secrets present but minting a token failed; running without a GitHub identity"
    return 1
  fi
  echo "WARNING: no $secrets_dir/$slug.json; running without a GitHub identity -- comments/labels use whatever ambient gh auth this shell has"
  return 1
}

# Where a role's per-run logs and its runs.tsv live.
agent_run_dir() { echo "${AGENT_CACHE_DIR:-$agent_main/.cache/$1}"; }

# One line per run in <runs_tsv>: what the run was for and what it cost, parsed from the log's
# last `result` event by agent_lib, so there is one implementation of "what did this run cost".
agent_append_run_row() {
  local logfile=$1 runs_tsv=$2 ts=$3 context=$4 model=$5
  [ -s "$runs_tsv" ] \
    || "$agent_python" -c 'from agent_os.lib import RUNS_TSV_HEADER; print(RUNS_TSV_HEADER)' >"$runs_tsv"
  "$agent_python" -m agent_os.lib planner-run-row "$logfile" \
    --ts "$ts" --context "$context" --model "$model" >>"$runs_tsv"
}

# A RULES paragraph rendered from config can come back empty -- a project that protects no path,
# or forbids no command -- and then the placeholder's own line goes with it, blank line included:
# a heading with nothing under it reads as a rule the agent cannot see, and substituting an empty
# string would leave a gap twice as wide as the paragraph it replaced. Lives here, above the
# sourcing guard, so this driver and worker_task.sh (which sources it) share one implementation.
agent_substitute_rules_paragraph() {
  local placeholder=$1 rendered=$2
  if [ -n "$rendered" ]; then
    RULES=${RULES//"$placeholder"/"$rendered"}
  else
    RULES=${RULES//"$placeholder"$'\n\n'/}
  fi
}

# Sourced for the helpers above (planner_task.sh) -- everything below is the driver itself.
[ "${BASH_SOURCE[0]}" != "${0}" ] && return 0

usage() { awk 'NR > 1 && /^#/ { print; next } NR > 1 { exit }' "$0"; }

# ---------------------------------------------------------------------------------------------
# The throwaway worktree of a role that runs tests (#393). A worktree made by `git worktree add`
# carries tracked files and no Python environment, and the run reviewed in
# `.cache/validator/20260916T182534Z.log` answered that by symlinking the MAIN checkout's `.venv`
# into it: that venv's editable install points at the MAIN checkout's package, so the suite the
# validator then ran measured code its review was not about. The driver makes the worktree itself,
# links the two gitignored files a run needs, and exports `PYTHONPATH` at the worktree, which is
# what makes that same venv resolve the worktree's own copy -- the rule docs/modules/workers.md
# states for a worker and worker_task.sh's launch already exports.
# ---------------------------------------------------------------------------------------------
agent_worktree=""

agent_remove_worktree() {
  [ -n "$agent_worktree" ] || return 0
  local path=$agent_worktree
  agent_worktree=""
  # --force because a run leaves untracked files behind (its own .cache, pytest's), and `prune`
  # after it because a registration that outlives the run is the next run's `git worktree add`
  # failing on a path that is already taken.
  git -C "$agent_main" worktree remove --force "$path" >/dev/null 2>&1
  git -C "$agent_main" worktree prune >/dev/null 2>&1
  if [ -e "$path" ]; then
    echo "WARNING: $path survived its removal -- remove it by hand"
  else
    echo "worktree:  removed $path"
  fi
}

# Creates, populates and exports the worktree, or degrades to ONE warning and no worktree: a
# validator that cannot run the tests still owes a review of the diff, and a criterion it could not
# settle is not a pass -- the same way a missing GitHub identity degrades rather than fails.
agent_prepare_worktree() {
  local role=$1 subject=$2 stamp=$3 path ref linked pull_ref
  # Its own PID in the name: two runs on one pull request, or one run re-launched inside the same
  # second, must not fight over one path.
  path=$(agent_run_dir "$role")/worktree-pr$subject-$stamp-$$
  if [ -n "${AGENT_WORKTREE_REF:-}" ]; then
    ref=$AGENT_WORKTREE_REF
  else
    # The pull request's own head: the branch need not exist in this checkout, and a worktree at
    # some other commit is the defect this whole function exists to prevent. Resolved by name and
    # never through FETCH_HEAD -- another process fetching in between leaves FETCH_HEAD pointing at
    # its own fetch -- and resolved BEFORE the fetch, so the fetch can only bring a commit at least
    # as new as the one named here.
    pull_ref="refs/pull/$subject/head"
    ref=$(git -C "$agent_main" ls-remote origin "$pull_ref" | awk 'NR == 1 { print $1 }')
    if [ -z "$ref" ]; then
      echo "WARNING: origin names no $pull_ref -- no worktree, so this run can read the diff and run nothing against it"
      return 1
    fi
    if ! git -C "$agent_main" fetch -q origin "$pull_ref"; then
      echo "WARNING: cannot fetch $pull_ref from origin -- no worktree, so this run can read the diff and run nothing against it"
      return 1
    fi
  fi
  if ! git -C "$agent_main" worktree add --detach "$path" "$ref" >/dev/null 2>&1; then
    echo "WARNING: no throwaway worktree at $path -- this run can read the diff and run nothing against it"
    return 1
  fi
  agent_worktree=$path
  # `git worktree add` brings tracked files only, and both of these are gitignored: without `.venv`
  # nothing runs at all (`scripts/test.sh` calls `.venv/bin/pytest`), and without `.env` a tool
  # that needs a credential refuses before it reaches the network. A link, never a copy -- one file
  # stays authoritative for every tree, exactly as worker_task.sh's launch does for a worker.
  for linked in .venv .env; do
    [ -e "$path/$linked" ] && continue
    [ -e "$agent_main/$linked" ] && ln -s "$agent_main/$linked" "$path/$linked"
  done
  export PYTHONPATH="$path"
  echo "worktree:  $path @ $(git -C "$path" rev-parse --short HEAD) (PYTHONPATH exported at it)"
}

# Waits, bounded, for a just-forked run to be in a session of its own -- `$1` is its PID, and its
# session ID equals it once `setsid` has run. Until then the run is still in THIS shell's process
# group and still carries this shell's traps, so a teardown of the group inside that window kills
# the run before it starts and its inherited trap removes the worktree it was about to own:
# measured 2026-09-17, one launch in three lost that race against a test that kills the launching
# shell as soon as the driver announces the run.
#
# RETURNS 0 once the run is in its own session; 1 if it ended before getting there (gone, or a
# zombie nobody has reaped -- the launch that never happened); 2 if it is alive and still in this
# shell's session after ~2s, which is a detach that has not taken and may never.
agent_wait_for_own_session() {
  local pid=$1 tries=0 sid state
  while [ $tries -lt 200 ]; do
    read -r sid state <<<"$(ps -o sid=,stat= -p "$pid" 2>/dev/null)"
    [ -z "${sid:-}" ] && return 1
    [ "$sid" = "$pid" ] && return 0
    case ${state:-} in *Z*) return 1 ;; esac
    tries=$((tries + 1))
    sleep 0.01
  done
  return 2
}

# ---------------------------------------------------------------------------------------------
# Where one run's own environment ENDS (#475). The launching half exports a description of ONE run
# -- the AGENT_RUN_* block, AGENT_DETACHED_RUN and the run-scoped PYTHONPATH -- and that description
# dies with the run. Two ways out of it are why this is code and not a comment. `agent_guard.py
# wake` hands its environment to the planner it starts (`_invoke_planner`, agent_guard.py:1999,
# passes no `env=`), and that planner hands it to every role it launches; and a role launched inside
# it met the detached re-entry below before one of its own arguments was parsed, so it ran the
# PREVIOUS role's brief over the PREVIOUS role's worktree -- frozen at the head that role cut, and
# removed under it -- wrote into the previous role's log, and left no row of its own in `runs.tsv`.
# The damage is not the waste, it is the silence: a review that read old code is indistinguishable,
# in the record, from a review that read the code it claims to have reviewed.
#
# Prints the NAMES, one per line, of the run-scoped variables in this shell's environment.
# PYTHONPATH is one of them only when it is a run's worktree, which this run's own EXIT trap is
# about to remove: a PYTHONPATH the caller had for its own reasons is the caller's and stays.
# ---------------------------------------------------------------------------------------------
agent_run_environment_names() {
  compgen -e | grep -E '^(AGENT_RUN_|AGENT_DETACHED_RUN$)'
  if [ -n "${AGENT_RUN_WORKTREE:-}" ] && [ "${PYTHONPATH-}" = "$AGENT_RUN_WORKTREE" ]; then
    echo PYTHONPATH
  fi
  return 0
}

# ---------------------------------------------------------------------------------------------
# The DETACHED half of one run (#400): everything that still has to happen after the backend
# exits -- the runs.tsv row, the planner event, the wake and the worktree's removal -- in the one
# process that outlives the shell which launched this driver. The driver re-enters itself under
# `setsid` with AGENT_DETACHED_RUN=yes, so this runs in a session of its own and reads every input
# from the AGENT_RUN_* environment the driver exported: nothing here is a positional argument,
# because the whole point is that no shell able to pass one is still alive.
# ---------------------------------------------------------------------------------------------
agent_detached_run() {
  agent_worktree=${AGENT_RUN_WORKTREE:-}
  # The two traps the driver installs before the detach, now covering the run that owns the
  # worktree: EXIT for a backend that fails, the signal trap for a run that is killed, which is the
  # one that would otherwise leave its worktree registered behind it.
  trap agent_remove_worktree EXIT
  trap 'agent_remove_worktree; exit 143' INT TERM HUP

  # Launched from the MAIN checkout: a one-shot role reads and judges, it never writes code. The
  # worktree above is where the commands it runs resolve, not where the backend itself sits.
  # `AGENT_RUN_LAUNCH_BACKEND` is the launch gate's answer and not the class's own backend (#425),
  # and `AGENT_RUN_MODEL` the model that goes with it -- which is also the model the runs.tsv row
  # below records, so a substituted run books its spend to the backend that actually spent it.
  agent_set_backend_flags "$AGENT_RUN_LAUNCH_BACKEND"
  "$AGENT_RUN_BACKEND" "${agent_backend_flags[@]}" --model "$AGENT_RUN_MODEL" \
    --append-system-prompt "$AGENT_RUN_RULES" \
    "$AGENT_RUN_INSTRUCTION" \
    >>"$AGENT_RUN_LOGFILE" 2>&1

  agent_append_run_row "$AGENT_RUN_LOGFILE" "$AGENT_RUN_DIR/runs.tsv" \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$AGENT_RUN_CONTEXT" "$AGENT_RUN_MODEL"

  if [ "$AGENT_RUN_NO_WAKE" = yes ]; then
    # A manual run a human wants to review before the planner acts on it: everything above (the
    # log, the runs.tsv row) is written as usual, but neither the event nor `wake` is -- the
    # planner never hears this run happened until the human is done looking at it.
    echo "no-wake: not writing ${AGENT_RUN_ROLE}_finished, not calling agent_guard.py wake"
  else
    # The role's own end is an edge the planner acts on, exactly like a worker's: write the event,
    # then knock on the one door (docs/adr/2026-09-14-the-planner-wakes-on-disk-events-and-an-idle-
    # wake-is-rate-limited.md). This is the step that never ran for PR #399's validator.
    # `${VAR-}` and not `$VAR`: this is the announcement PR #399's run never made, and a suffix
    # the launching half did not export must not be what stops it.
    #
    # Both calls LEAVE this run, so neither takes this run's environment with it (#475): the wake
    # starts a planner in whatever it is handed, and a role that planner launches would otherwise
    # be met by an environment still describing the run that just ended. `env -u` and not `unset`:
    # the event's own arguments are this shell's to expand, and the detached half still needs the
    # block after both calls -- removing its PID file is the last thing it does.
    local -a outside_the_run=()
    local leaked
    while read -r leaked; do outside_the_run+=(-u "$leaked"); done < <(agent_run_environment_names)
    env "${outside_the_run[@]}" \
      "$agent_python" -m agent_os.guard event \
      "${AGENT_RUN_ROLE}_finished" "$AGENT_RUN_SUBJECT" \
      --detail "the $AGENT_RUN_ROLE finished on #$AGENT_RUN_SUBJECT${AGENT_RUN_FINISHED_SUFFIX-}"
    env "${outside_the_run[@]}" \
      "$agent_python" -m agent_os.guard wake
  fi

  # The run reached its own end, so its PID file goes with it: a PID file still sitting beside a log
  # that holds no `result` event is a run that DIED, and that is the signal the guard reads (#400).
  rm -f "$AGENT_RUN_PIDFILE"
}

# Below this line the file is the driver itself; above it, the helpers everyone gets by sourcing
# it. The detached half re-enters here, before anything is parsed, resolved or minted a second
# time: its inputs already arrived through the environment the launching half exported, and that
# half passes it NO ARGUMENT -- `setsid nohup bash "$agent_os_dir/bin/agent_task.sh"`, below.
# Carrying no argument is therefore the whole signature of the re-entry, and it is what tells the
# driver's own second half from a role somebody is launching: an invocation that DOES carry
# arguments is a role of its own, with its own brief, its own worktree, its own log and its own
# runs.tsv row, however stale an AGENT_DETACHED_RUN in its environment happens to be (#475).
if [ "${AGENT_DETACHED_RUN:-no}" = yes ] && [ $# -eq 0 ]; then
  agent_detached_run
  exit 0
fi

# A launch forgets the run it was launched from: every one of these names is re-exported for the
# new run below, and a PYTHONPATH left pointing at an earlier run's worktree -- which for a role
# that runs no tests nothing overwrites -- would have the backend resolve its imports in a tree
# that is not the one it was told to work in.
stale_run_variable=""
while read -r stale_run_variable; do
  [ -n "$stale_run_variable" ] && unset "$stale_run_variable"
done < <(agent_run_environment_names)

role=""; subject=""; dry_run=no; no_wake=no; runs_tests=no; context_parts=()
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) dry_run=yes ;;
    --no-wake) no_wake=yes ;;
    -h|--help) usage; exit 0 ;;
    *)
      if [ -z "$role" ]; then role=$1
      elif [ -z "$subject" ]; then subject=$1
      else context_parts+=("$1"); fi
      ;;
  esac
  shift
done
context=${context_parts[*]:-}

[ -n "$role" ] || { usage; exit 2; }
case "$subject" in
  ''|*[!0-9]*) echo "usage: $0 <role> <issue|pr> [context...] [--dry-run] [--no-wake]  -- the subject is a number"; exit 2 ;;
esac

# The class carrying `role: <role>`. A role with no class of its own (or with two) is a
# configuration error and stops here rather than being guessed at.
class_name=$(agent_role_field "$role" name) || exit 1
backend=$(agent_role_field "$role" backend) || exit 1
[ "$backend" = claude ] || {
  echo "role '$role' is configured for backend '$backend'; this driver only runs the claude CLI"
  exit 1
}
# ... and which backend THIS run gets, which is the class's own unless the guard's persisted quota
# verdict says that backend is exhausted and the class declares a way round it (#425). `model` is
# the gate's answer from here on, never the class's field read a second time: the two are the same
# string on an unsubstituted run and deliberately different on a substituted one.
agent_read_launch_gate "$role" || exit 1

# The injected contract, one block per role -- the task itself is the subject and its own issue,
# exactly as a worker's task is its issue.
case "$role" in
validator)
  # The one role that runs anything: the criteria of the issue it reviews are settled by tests, so
  # it gets a throwaway worktree of the pull request's own head (#393).
  runs_tests=yes
read -r -d '' RULES <<'PROMPT'
You are running headless as the VALIDATOR. Your task is ONE pull request: you check it, criterion
by criterion, against the acceptance criteria and the definition of done of the issue it closes,
and you post exactly ONE pull request review saying what you found. You did not write this code
and you are not going to: every line below is a hard constraint.

WHAT YOU NEVER DO
- You never edit, stage or commit a file anywhere. Not a fix, not a typo, not a missing test.
  A gap is something you report in the review, never something you close yourself.
- You never merge, never push, never close the pull request or its issue, and never change a
  label other than the two moves named at the end of this block.
- You never comment on the issue or the pull request outside your one review. One run, one
  review: a second comment is how a reviewer's own noise becomes the thing the human has to read.
- `pytest` writes to the shared database for real, so check no other pytest is alive first
  (`ps -eo pid,cmd | grep [p]ytest`) and never start a second one.

__NEVER_RUN_RULES__

WHAT YOU READ, IN THIS ORDER
1. `AGENTS.md` in this checkout -- the project's own rules are the floor under every criterion.
2. The issue behind the pull request. `gh pr view <pr> --json body,title,headRefName,baseRefName`
   gives you the body; the `Closes #N` line in it names the issue. Then
   `__ISSUES_CLI__ brief N` for the issue AND its parent, which is exactly
   what the worker was given -- you are checking the same contract it was handed.
3. The diff: `gh pr diff <pr>`. Read it whole. The diff is the evidence; the pull request body
   and the worker's own report are claims about it.
4. Only the docs, ADRs and paths the issue itself names. Nothing else.

HOW YOU CHECK
- One verdict per acceptance criterion, and one per line of the definition of done. Never a
  verdict on the change "overall".
- A criterion is met when you can point at the thing that meets it: a path and a line in the
  diff, a command you ran and its output, a test name and its result. "It looks implemented" is
  not a verdict, it is a guess.
- Everything you run against the pull request's code runs inside the throwaway worktree the
  driver prepared for this run, and nowhere else. Its path is __WORKTREE__. That worktree holds
  the pull request's own head, it is already populated with the environment its commands need,
  and the driver removes it when this run ends: making it and cleaning it up are the driver's,
  never yours.
- When that is not a path you can enter, the driver prepared no worktree for this run and
  printed its own WARNING saying why. Read the diff then, and run nothing: every criterion that
  needed a run is a criterion you could not settle, which is not a pass and is not a reason to
  prepare an environment of your own.
- Run `ruff` on the Python files the pull request actually touches, never on the whole
  repository (this repo is not lint-clean globally -- that is tracked separately), and run it
  from inside that worktree: `.venv/bin/ruff check <files>` and
  `.venv/bin/ruff format --check <files>`. The same file in this checkout is not the code under
  review, and linting it is a verdict about something else.
- Run the tests the ISSUE names, and only those, from inside that worktree as well. Run the full
  suite ONLY if the issue's own definition of done says so -- it takes ~50 minutes and running it
  uninvited is how a review costs more than the work it reviews.
- Never drop `PYTHONPATH`: not unset, not reassigned, not left behind by a shell you start
  yourself (`env -i`, a login shell, a wrapper). The driver exported it at that worktree and it
  is what makes the environment resolve the worktree's own package instead of this checkout's, so
  a run that loses it still executes, still prints results, and still measures code your review
  is not about. Before you trust any result, check it from inside the worktree: `echo
  "$PYTHONPATH"` prints that same path.
- Never prepare an environment of your own to run in: no new worktree, no checkout of the branch,
  and nothing that links or copies this checkout's `.venv` or `.env` into one. A venv you linked
  yourself carries an editable install pointing at the tree it came from, which is how the run
  these rules were written after measured one tree and reported on another.
- Never check the branch out in this checkout, and never touch either worker's worktree.
- The issue's own `## Stages` checklist is a checkable claim, not prose: inside that worktree,
  `git log --format=%s <base>..<head>` must show one `stage N/M: <title>` commit per
  line of the checklist, in the same order, and the LAST one's own N must equal M. A branch short
  of its own last stage is unfinished work -- never a pass, whatever the diff otherwise looks like.
- A criterion you cannot settle is NOT a pass. Say what you tried, what stopped you, and what
  would settle it.
- A criterion the code does not meet has two possible causes, and picking one without checking is
  how a review sends good code back: the code is wrong, or the criterion is. A criterion was
  written before the code existed, and what the work itself taught can have made it obsolete. So
  before you report one as unmet, check its premise: read what the code actually does, and read
  the bodies of the issues that consume it rather than assuming who its callers are. When the
  criterion is the stale half, report THAT -- the criterion, the evidence against it, and what it
  should say instead. You still never edit it: naming it is the review's job, changing it is the
  human's.

THE ONE REVIEW YOU POST
Exactly one call, and it is the only thing you publish:
  `gh pr review <pr> --approve --body-file <file>` when every criterion and every definition-of-
  done line is met; otherwise `gh pr review <pr> --request-changes --body-file <file>`.
The body's FIRST line names the backend that wrote it, verbatim and on its own line, then a blank
line:

    __REVIEW_BACKEND_LINE__

(When there is a `## Doubts` block, the `@` mention described below is the first line and this one
comes right after it.) A review that does not say which backend wrote it is one nobody can
attribute afterwards, neither in the tracker nor in the spend report, and a run substituted onto a
fallback backend is exactly the one a reader has to be able to recognise.
The body is a checklist, one line per criterion, in the issue's own order, each followed by its
evidence indented under it:

    - [x] <the criterion, quoted from the issue>
          agent_os/bin/agent_task.sh:112 -- the driver resolves the role's class before running
    - [ ] <the criterion, quoted from the issue>
          `scripts/test.sh tests/test_agent_task.py` -> 3 failed, 4 passed -- <the failing name>

Then a `## Stages` block in the same shape -- one line per stage naming its own `stage N/M:` commit
found (or missing) -- a `## Definition of done` block, and last a `## Doubts` block naming anything
you could not settle (omit it when there is none), written the way the paragraph below describes.
Quote what you ran and what came back; a number you did not measure in this run is not evidence.

__HUMAN_MESSAGE_RULES__

WHAT HAPPENS AFTER THE REVIEW
- Approved: `__ISSUES_CLI__ move N review`. The human merges -- merging is
  never an agent's act (docs/adr/2026-08-26-the-agent-proposes-the-human-publishes.md).
- Changes requested: change NOTHING. Leave the issue's label exactly as it is. The planner reads
  your review and resumes the worker with it as context; your review body is the worker's next
  brief, so write it for the worker, not for the record.
- A doubt only a human can settle (the issue contradicts an ADR, a criterion is ambiguous, the
  change touches something the issue never mentioned): say so in the `## Doubts` block of the
  same review, then `__ISSUES_CLI__ move N blocked-on-human`. Still one
  review, still no separate comment -- and when there is a `## Doubts` block the review body
  STARTS with `@__HUMAN_LOGIN__`, on its own first line, because a question that is not a mention
  does not reach the human's GitHub mentions and waits on an issue nobody is watching.
PROMPT
  first_instruction="Validate pull request #$subject. Read AGENTS.md, then the issue it closes and
its parent (the brief the worker was given), then the diff; check every acceptance criterion and
every definition-of-done line; post exactly one review and then exit. Context from the planner: ${context:-(none)}"
  ;;
refiner)
  # It writes issues and never runs code, so it is the one role launched with no worktree at all.
read -r -d '' RULES <<'PROMPT'
You are running headless as the REFINER. Your task is ONE issue: turn a raw backlog issue into
template-conformant, STAGED sub-issues, each with a budget class -- or, when it is already small
enough to be one reviewable piece of work, rewrite its own body into that shape and stage it. You
never write code and you never touch the shared database: every line below is a hard constraint.

WHAT YOU READ, IN THIS ORDER
1. `AGENTS.md` in this checkout -- the project's own rules are the floor under anything you write.
2. `__ISSUES_CLI__ brief N` for the issue AND its parent -- the same contract a
   worker or the validator is handed. N is the subject of this run.
3. Only the docs, ADRs and paths those two bodies name. Nothing else -- a refiner that goes looking
   for more context is doing the worker's own reading for it.
4. Before you choose a budget class for anything you write, read the `classes:` section of
   `config/agents.yaml`. A class carrying `role: <name>` (validator, refiner, planner) is that
   role's own ceiling, never a work budget for a task or bug -- pick among the classes that carry
   no `role:` field. EVERY worker task goes to a Qwen class: `mechanical-qwen` when the change is
   small and fully specified, `complex-qwen` in every other case. Never give a worker task a class
   whose `backend:` is `claude`
   (docs/adr/2026-09-16-workers-run-on-qwen-and-claude-only-reviews.md).

WHAT YOU NEVER DO
- You never edit, stage or commit a file anywhere -- you write issues, never code.
- You never merge, never push.
- You never set `status:ready` on anything: only the planner or the human does that
  (docs/adr/2026-09-14-the-issue-is-the-unit-of-work-and-status-labels-are-the-mechanical-
  state.md). A refined issue stays `status:refine`, for the human or for the mechanical promotion
  under its parent's `auto-ready` label -- neither is your call.
- You never add or remove `status:agents-paused` -- the human-only full stop.

__NEVER_RUN_RULES__

DECIDE THE SHAPE
- A task or bug that is already ONE reviewable pull request touching ONE module: rewrite its body
  in place. BEFORE rewriting, post the ORIGINAL body verbatim as a comment on the issue
  (`__ISSUES_CLI__ update N --comment "<the original body>"`) so nothing is
  lost, THEN write the new body: `__ISSUES_CLI__ update N --body-file <file>`.
- A feature, or a task/bug spanning more than one module or more than one reviewable pull request:
  create sub-issues, one per reviewable piece of work --
  `__ISSUES_CLI__ create --type task|bug --title T --parent N --body-file
  <file>` -- then move each one into refine: `__ISSUES_CLI__ move <child>
  refine`. Never rewrite a feature's own body; a feature has no template shape to conform to.
  Once every child exists, take the ORIGINAL's own refine label off so it is never refined a second
  time: `__AGENT_OS_LIB_CLI__ project-value labels.refine` prints the exact label
  spelling to remove, then `__ISSUES_CLI__ update N --remove-label <that
  label>`.

STAGE THE WORK -- EVERY BODY YOU WRITE OR REWRITE NEEDS A WELL-FORMED `## Stages` SECTION
Without one, an issue is not dispatchable however good every other section already is -- which is
exactly why you are called on an issue that already looks conformant, not only on a raw one: this
section is the one thing nothing but you (or a human) can write. Write it INSIDE the body you are
already rewriting, or inside each sub-issue you create -- never split an issue into sub-issues for
this alone, only when the work itself spans more than one module. How to fraction the work is YOUR
decision, case by case, after reading the issue and the Context it names; these are the principles
that decision runs on, never a size or a count:
- A stage is a small unit of work that leaves the tree green (tests pass) and committed, small
  enough that a fresh process can complete it with minimal complexity.
- That fresh process is handed the FULL issue body and the Context it names, whichever stage it is
  running -- context is never the constraint on how small a stage can be. The WORK is: a stage is
  small because doing it and closing it with a commit is a short, self-contained step, not because
  the process reading it is starved of anything.
- Each stage names the files it touches and how it is verified (a test file, a command, a check a
  reader can run) -- the checklist line alone must say what "done" looks like for that stage.
- Order stages so the test scaffolding the rest of the work depends on comes early, and any
  documentation update comes last -- a later stage should never need a harness an earlier one
  skipped.
- No numeric floor or ceiling: the issue's own shape decides how many stages it gets and how big
  each one is, never a rule of thumb.
Write it as the ordered checklist the template shows, one `- [ ]` line per stage, its own text
naming the deliverable (`agent_os.lib`'s `parse_stages` reads exactly that shape, and
`section_failures` rejects a `## Stages` heading with no such line as `stages: no checklist line`).

EVERY BODY YOU WRITE
- The seven sections, in this exact order, with these exact English headings: `## Objective`,
  `## Acceptance criteria`, `## Stages`, `## Context`, `## Not included`, `## Dependencies`,
  `## Definition of done` -- then the line `<!-- budget: <class> -->` last.
  `.github/ISSUE_TEMPLATE/task.md` and `bug.md` are the scaffold this must match.
- English content -- AGENTS.md's own language rule: code, identifiers and repository documentation
  are English regardless of what language the human's own conversation is in.
- If the original body carries a `<!-- key: ... -->` line, the rewritten body keeps it verbatim --
  the loader finds issues by it, and dropping it orphans the issue from whatever created it.
- `## Dependencies` as `Blocked by #N` lines, one per line, or the single word `none`.
- If the work collides with a rule in `AGENTS.md` (a freeze the project declares, a file it
  protects, anything the Context section made you read that says "never"), say so in
  `## Not included` or `## Dependencies` AND as a doubt at the end -- never invent a workaround
  around a rule you were told to respect.

AFTER WRITING, VALIDATE EVERYTHING YOU WROTE
`__ISSUES_CLI__ validate <N>` on every issue you wrote or rewrote -- every one
must print `ok`. One that still fails after your own pass is a doubt (below), never something you
leave silently broken.

THE ONE SUMMARY COMMENT
Exactly one summary comment on the ORIGINAL issue -- the only thing you post there besides the
preserved-body comment above. Its first line is the fixed marker `<!-- refiner-summary -->`, in
its own spelling, so nothing launches the refiner on this issue again once it carries one
(docs/adr/2026-09-15-the-refiner-runs-unattended-only-after-a-human-reviewed-its-dry-run.md). Then:
what shape you chose and why, the list of issues you wrote or rewrote with each one's budget class,
and a `## Doubts` block if you have one (omit it when you have none), written the way the paragraph
below describes. When there is a doubt, the line right after the marker is `@__HUMAN_LOGIN__` on
its own, so it reaches the human's GitHub mentions, and you then run
`__ISSUES_CLI__ move N blocked-on-human`. Otherwise every refined issue stays
`status:refine`, waiting for the human or the mechanical promotion to move it on to `status:ready`
-- you never set that label yourself.

__HUMAN_MESSAGE_RULES__

Your whole summary comment -- not only its `## Doubts` block -- is written in that language, right
after the fixed marker line; only the marker itself keeps its own spelling. The issue bodies you
write or rewrite (including every sub-issue) stay in English regardless, per AGENTS.md's own
language rule -- this rule is about what you say TO the human, never about what you write INTO the
tracker.
PROMPT
  first_instruction="Refine issue #$subject. Read AGENTS.md, then \`issues.py brief $subject\` for
the issue and its parent, then only the docs and paths they name. Decide whether it is one
reviewable task/bug (rewrite its body in place, after preserving the original as a comment) or a
feature/multi-piece issue (split into template-conformant sub-issues, each moved to status:refine,
then remove the original's own refine label). Validate everything you write, then post exactly one
summary comment starting with the marker <!-- refiner-summary -->. Context from the planner: ${context:-(none)}"
  ;;
*)
  echo "no RULES block for role '$role'. A worker runs under agent_os/bin/worker_task.sh and the"
  echo "planner under agent_os/bin/planner_task.sh; this driver runs the one-shot roles only."
  exit 2
  ;;
esac

# The one human's login is project config, never a literal in a script; the RULES heredocs above
# are quoted on purpose, so it is substituted here rather than expanded there
# (docs/adr/2026-09-14-the-agent-mechanism-is-project-agnostic-and-configured-not-coded.md).
RULES=${RULES//__HUMAN_LOGIN__/$(agent_project_value human_login)}
RULES=${RULES//__HUMAN_MESSAGE_RULES__/$("$agent_python" -m agent_os.lib human-message-rules)}
# The tracker CLI and the config reader, as an absolute interpreter plus the module: a role's
# shell does not carry this package's `bin/` on its PATH, and a prompt cannot name a shell
# variable. One substitution, so the command an agent is told to run is the command the
# mechanism itself runs (`agent_os/bin/_python.sh`).
RULES=${RULES//__ISSUES_CLI__/$(agent_os_issues_cli)}
RULES=${RULES//__AGENT_OS_LIB_CLI__/$(agent_os_lib_cli)}
# Which commands write something shared is the project's own knowledge, never the mechanism's: one
# list in `project.never_run`, rendered into both blocks above rather than spelled twice in them
# (docs/adr/2026-09-14-the-agent-mechanism-is-project-agnostic-and-configured-not-coded.md).
agent_substitute_rules_paragraph __NEVER_RUN_RULES__ \
  "$("$agent_python" -m agent_os.lib never-run-rules)"

# The line a validator's review body starts with, naming the backend that wrote it (#425). The
# merge gate accepts a substituted review as the validator's approval -- the human's decision of
# 2026-09-18, recorded beside the `fallback:` declaration in config/agents.yaml -- so what the
# substitution must not lose is the record of itself: the gate reads a review by the App that
# signed it, and the App comes from `project.role_apps`, never from the backend that ran.
review_backend_line="Reviewed by the validator on $launch_backend ($model)."
if [ "$launch_substituted" = yes ]; then
  review_backend_line="Reviewed by the validator on $launch_backend ($model), the fallback backend its class declares because the guard's persisted $backend quota verdict read exhausted. This review IS the validator's approval for the merge gate (the human's decision of 2026-09-18)."
fi
RULES=${RULES//__REVIEW_BACKEND_LINE__/$review_backend_line}

identity_slug=$("$agent_python" -m agent_os.lib role-app "$role") || exit 1
secrets_dir=$(agent_project_value --path secrets_dir) || secrets_dir=""

echo "role:      $role (class $class_name)"
agent_backend_identity_line "$backend"
echo "model:     $model"
echo "subject:   #$subject"
echo "context:   ${context:-(none)}"
echo "launch:    $launch_reason"

if [ "$dry_run" = yes ]; then
  # Resolved, printed, and nothing spent: no token is minted and no backend is called. No worktree
  # is prepared either, so the placeholder says that instead of staying in the prompt.
  RULES=${RULES//__WORKTREE__/'none -- a dry run prepares no worktree'}
  if [ -n "$secrets_dir" ] && [ -f "$secrets_dir/$identity_slug.json" ]; then
    echo "identity:  $identity_slug (secrets present)"
  else
    echo "identity:  $identity_slug (no secrets -- would run with the ambient gh identity)"
  fi
  echo "--- prompt ---"
  echo "$first_instruction"
  echo "--- rules ---"
  echo "$RULES"
  exit 0
fi

agent_apply_identity "$identity_slug"

run_stamp=$(date -u +%Y%m%dT%H%M%SZ)
run_dir=$(agent_run_dir "$role")
logfile=$run_dir/$run_stamp.log
# The run's PID, beside the log of the same stamp -- `.pid` for `.log` is the whole of the contract
# the guard reads (#400): a PID that is dead with no `result` event in that log is a run that died.
pidfile=$run_dir/$run_stamp.pid
# Resolved before the log header is written, so a broken config stops the run where it can still
# be read as a refusal rather than as a backend that would not start (#380). WHICH binary is the
# launch gate's answer: one environment override per backend, so a test can stub the fallback
# without stubbing the class's own backend and lose track of which of the two ran (#425).
case "$launch_backend" in
  claude) backend_bin=$(agent_executable claude "${AGENT_CLAUDE_BIN:-}") || exit 1 ;;
  qwen) backend_bin=$(agent_executable qwen "${AGENT_QWEN_BIN:-}") || exit 1 ;;
  *)
    echo "the launch gate named a backend this driver cannot run: '$launch_backend'"
    exit 1
    ;;
esac

mkdir -p "$run_dir"
{
  echo "ts:        $run_stamp"
  echo "role:      $role (class $class_name)"
  agent_backend_identity_line "$backend"
  echo "model:     $model"
  echo "subject:   #$subject"
  echo "context:   ${context:-(none)}"
  echo "launch:    $launch_reason"
} >>"$logfile"

# Removed on EVERY exit path up to the detach below. A backend that will not start does not stop
# this script (there is no `set -e` here), so the EXIT trap covers a failed launch; the signal trap
# covers a driver killed before it detached. Past the detach both traps are the detached run's own
# (`agent_detached_run`), because the worktree belongs to that run and not to this shell any more.
trap agent_remove_worktree EXIT
trap 'agent_remove_worktree; exit 143' INT TERM HUP

if [ "$runs_tests" = yes ]; then
  agent_prepare_worktree "$role" "$subject" "$run_stamp"
  [ -n "$agent_worktree" ] && echo "worktree:  $agent_worktree" >>"$logfile"
  # The RULES name that worktree by its own path instead of leaving the agent to derive it: on the
  # run that prepared none, an inherited `$PYTHONPATH` still points at whatever tree launched this
  # driver, and `git worktree list` names every other run's worktree beside this one's.
  if [ -n "$agent_worktree" ]; then
    RULES=${RULES//__WORKTREE__/"$agent_worktree"}
  else
    RULES=${RULES//__WORKTREE__/'none -- the driver could not prepare one and printed its own WARNING above'}
  fi
fi

# -------------------------------------------------------------------------------------------------
# The detach (#400). Until here everything this driver did was preparation, and all of it stays in
# this shell so that whoever launched it reads the resolution, the identity and any worktree
# WARNING on its own stdout. What follows is the run, and the run is not this shell's to hold: a
# planner that launches a validator through its Bash tool gets that command moved to the background
# on the tool's own timeout and then exits, and a run inside the exiting session's process group
# dies with it -- mid-turn, with no `result` event, no `validator_finished` and no review on the
# pull request, which is exactly what PR #399 was left with.
#
# `setsid` gives the run a session of its own, so no teardown of this shell's group can reach it;
# `nohup` makes the SIGHUP such a teardown sends harmless; `</dev/null` stops it from ever reading
# a terminal that is gone. The driver re-enters itself for the run's own half rather than passing a
# script body to `bash -c`, so the backend call and the bookkeeping after it stay in this file,
# under the same helpers, with one implementation.
# -------------------------------------------------------------------------------------------------
export AGENT_DETACHED_RUN=yes
export AGENT_RUN_ROLE="$role" AGENT_RUN_SUBJECT="$subject" AGENT_RUN_MODEL="$model"
export AGENT_RUN_BACKEND="$backend_bin" AGENT_RUN_RULES="$RULES"
export AGENT_RUN_LAUNCH_BACKEND="$launch_backend"
# The `<role>_finished` event is what brings the planner back to this run, so a substituted run
# says so in the event's own text: the planner is the one actor that has to know a review came from
# the fallback backend, and it reads that event and nothing else (#425). Empty unless the run was
# substituted, so the line an unsubstituted run writes is the one it has always written.
AGENT_RUN_FINISHED_SUFFIX=""
if [ "$launch_substituted" = yes ]; then
  AGENT_RUN_FINISHED_SUFFIX=" (ran on $launch_backend, the declared fallback for $backend)"
fi
export AGENT_RUN_FINISHED_SUFFIX
export AGENT_RUN_INSTRUCTION="$first_instruction" AGENT_RUN_CONTEXT="$role #$subject ${context:-}"
export AGENT_RUN_DIR="$run_dir" AGENT_RUN_LOGFILE="$logfile" AGENT_RUN_PIDFILE="$pidfile"
export AGENT_RUN_WORKTREE="$agent_worktree" AGENT_RUN_NO_WAKE="$no_wake"

setsid nohup bash "$agent_os_dir/bin/agent_task.sh" >>"$logfile" 2>&1 </dev/null &
run_pid=$!
# `$!` is the run's own PID and its session ID: `setsid` only forks when the process it starts is
# already a process-group leader, which a background job of a non-interactive shell never is -- the
# same idiom, and the same reading of `$!`, worker_task.sh's launch already relies on. The test in
# tests/test_agent_task.py measures it rather than trusting it.
#
# Announced only once it has TAKEN: until `setsid` has run, the pid below is still reachable by a
# teardown of this shell's process group, and whoever reads this shell's stdout is exactly whoever
# is about to tear that group down.
agent_wait_for_own_session "$run_pid"
detach_state=$?
printf '%s\n' "$run_pid" >"$pidfile"
echo "pid:       $run_pid (detached)" >>"$logfile"
case $detach_state in
  1)
    # A launch that never happened is a loud stop here, not a silent PR nobody reviews: the log
    # says why, and the PID file stays so the guard reports the run that died (#400).
    echo "WARNING: the run (pid $run_pid) ended before it left this shell's session -- read $logfile for why"
    ;;
  2)
    echo "WARNING: pid $run_pid is still in this shell's session 2s on -- a teardown of this shell can still reach it"
    ;;
esac
trap - EXIT
trap - INT TERM HUP

echo "detached:  pid $run_pid in a session of its own -- it outlives this shell"
echo "pidfile:   $pidfile"
echo "log $logfile"
