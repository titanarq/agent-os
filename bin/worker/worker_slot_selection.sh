#!/usr/bin/env bash
# Which worker slot a `worker_task.sh` call addresses, and the making of a new one when a dispatch
# finds none free (#90; agent_os/docs/adr/2026-10-09-worker-slots-are-created-on-demand.md).
# Sourced by the driver; it needs `use_slot`, `alive`, `alive_pidfile`, `hide_scratchpad_from_git`,
# `uncommitted_work` and `agent_os_init_worktree` from it, and defining the functions runs nothing.
#
# The slots of a backend are numbered, not counted: they can be sparse (a worktree removed by hand),
# so every loop walks `slot_numbers` and never `seq 1 N`.

# One `<backend> <slot> <key> <worktree>` line per slot of THIS backend, derived by `agent_os.lib`
# -- the same derivation the guard reads, so the two can never name a slot's files differently --
# and including the slots the driver made on demand. A backend with no worktree has no slot line at
# all, and is slot 1 on an empty worktree, which is what every refusal has always said about it
# (`no worktree at`). Run again after a slot is made.
load_slot_tables() {
  local slot_number slot_key slot_worktree
  slot_keys=("")
  slot_worktrees=("")
  slot_numbers=()
  while IFS=$'\t' read -r _ slot_number slot_key slot_worktree; do
    [ -n "$slot_number" ] || continue
    slot_keys[slot_number]=$slot_key
    slot_worktrees[slot_number]=$slot_worktree
    slot_numbers+=("$slot_number")
  done < <("$agent_python" -m agent_os.lib worker-slots "$backend" 2>/dev/null)
  if [ "${#slot_numbers[@]}" -lt 1 ]; then
    slot_numbers=(1)
    slot_keys[1]=$backend
    slot_worktrees[1]=$(backend_value "$backend" worktree --path)
  fi
  slot_count=${#slot_numbers[@]}
}

# Every slot's recorded issue and whether it is alive, for a refusal that has to say which slot to
# name. Leaves the slot variables on the last slot listed; every caller exits right after.
list_slots() {
  local n
  for n in "${slot_numbers[@]}"; do
    use_slot "$n"
    printf '  --slot %s  %s  %s, issue %s\n' "$n" "$worktree" \
      "$(alive && echo "running pid $(cat "$pidfile")" || echo idle)" \
      "$(cat "$issuefile" 2>/dev/null | sed 's/^/#/' || true)"
  done
}

# A slot `start` or `branch` may take: not alive, and a worktree there to work in. Leaves the slot
# variables on the last slot looked at.
slot_is_free() {
  use_slot "$1"
  ! alive && [ -e "$worktree/.git" ]
}

# Every worker alive across every slot of every backend: what `planner.max_parallel_issues`, when a
# host sets one, is compared against before a slot is made for one more.
alive_worker_count() {
  local count=0 other
  while IFS=$'\t' read -r _ _ other _; do
    [ -n "$other" ] && alive_pidfile "$cache/worker_$other.pid" && count=$((count + 1))
  done < <("$agent_python" -m agent_os.lib worker-slots)
  echo "$count"
}

# THE NEXT SLOT, MADE BECAUSE EVERY ONE IS BUSY: a number of slots is never a reason to refuse a
# dispatch, so the driver makes the worktree the way `init` makes one (the host's links, setup
# command and mechanism venv included) and the dispatch goes on in it. `agent_os.product.dispatch
# new-slot` says which slot that is, or why none -- the host's own cap, the backend's quota, names
# already taken -- and nothing is written then. The lock keeps two dispatches that both found
# nothing free from making the same slot; the second one reads the tables again under it.
make_the_next_slot() {
  local line number key path
  if command -v flock >/dev/null 2>&1; then
    exec 9>"$cache/worker_slots.lock"
    flock 9 || { echo "refusing to create a slot: could not lock $cache/worker_slots.lock"; exit 1; }
  fi
  load_slot_tables
  line=$("$agent_python" -m agent_os.product.dispatch new-slot "$backend" \
    --alive-workers "$(alive_worker_count)" --cache-dir "$cache" 2>&1) || { echo "$line"; exit 1; }
  IFS=$'\t' read -r _ number key path <<<"$line"
  agent_os_init_worktree "$main" "$path" "agent-os/init-$key" || exit 1
  load_slot_tables
  exec 9>&-
  echo "slot $number of backend '$backend' made on demand: every other slot is busy ($path)"
  use_slot "$number"
}

# THE FREE SLOT A DISPATCH TAKES, most specific first: one whose worktree is already on the branch
# this work belongs on (`branch_wanted`, the exact name `branch` was asked for, or `issue_wanted`,
# the planner's `<word>/<issue>-<slug>` shape `start`'s base gate accepts) -- which is what makes
# the planner's `branch task/<N>-<slug>` and the `start <N>` after it land on the SAME slot; then a
# clean one holding no cut run awaiting its relaunch; then any clean one; then the first free one,
# whose refusal (`worktree is dirty`) then says what is wrong with it. With none free, the next
# slot is made (`make_the_next_slot`), written before anything else is. `WORKER_WORKTREE` pins
# every slot to one tree, so there is nothing to make: the slot's own refusal is what answers.
pick_free_slot() {
  local issue_wanted=$1 branch_wanted=$2 n current free=() clean_uncut="" clean="" any_worktree=""
  for n in "${slot_numbers[@]}"; do
    use_slot "$n"
    [ -e "$worktree/.git" ] && any_worktree=yes
    if [ -n "$issue_wanted" ] && alive && [ "$(cat "$issuefile" 2>/dev/null || true)" = "$issue_wanted" ]; then
      echo "a run is already alive (pid $(cat "$pidfile")) on issue #$issue_wanted in slot $n; stop it first"
      exit 1
    fi
    slot_is_free "$n" || continue
    free+=("$n")
    current=$(git -C "$worktree" branch --show-current 2>/dev/null || true)
    if [ -n "$branch_wanted" ] && [ "$current" = "$branch_wanted" ]; then
      use_slot "$n"; return 0
    fi
    if [ -n "$issue_wanted" ] \
      && printf '%s\n' "$current" | grep -qE "(^|/)[a-z][a-z0-9-]*/$issue_wanted([-/]|$)"; then
      use_slot "$n"; return 0
    fi
    hide_scratchpad_from_git
    [ -z "$(uncommitted_work)" ] || continue
    [ -n "$clean" ] || clean=$n
    if [ -z "$clean_uncut" ] && ! grep -q '^CUT_BY_GUARD' "$statefile" 2>/dev/null; then
      clean_uncut=$n
    fi
  done
  if [ "${#free[@]}" -eq 0 ]; then
    # No worktree in any slot is the refusal every subcommand has always given: the first slot's.
    if [ -z "$any_worktree" ] || [ -n "${WORKER_WORKTREE:-}" ]; then use_slot "${slot_numbers[0]}"; return 0; fi
    make_the_next_slot
    return 0
  fi
  use_slot "${clean_uncut:-${clean:-${free[0]}}}"
}

# THE SLOT WHOSE RECORDED ISSUE IS THIS ONE, for `--issue <N>` (`resume`, `collect`, `open-pr`,
# `stop`, `watch`): the command addresses the run that recorded the issue, in the worktree that
# holds its branch. The newest record wins when
# two slots have run the same issue at different times.
pick_slot_of_issue() {
  local wanted=$1 n found="" found_file=""
  for n in "${slot_numbers[@]}"; do
    use_slot "$n"
    [ "$(cat "$issuefile" 2>/dev/null || true)" = "$wanted" ] || continue
    if [ -z "$found" ] || [ "$issuefile" -nt "$found_file" ]; then
      found=$n
      found_file=$issuefile
    fi
  done
  if [ -z "$found" ]; then
    echo "$subcommand refused: no slot of backend '$backend' recorded issue #$wanted"
    list_slots
    exit 1
  fi
  use_slot "$found"
}
