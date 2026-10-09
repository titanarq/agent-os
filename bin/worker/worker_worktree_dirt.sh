#!/usr/bin/env bash
# What a worker's worktree holds that is not its committed work, and what the driver does about it.
# Sourced by worker_task.sh, which owns the variables read here (`worktree`, `cache`, `slot_key`,
# `statefile`, `issuefile`, `agent_python`, `DIARY`, `WIP_SUBJECT`) and `alive`; defining the
# functions runs nothing.
#
# The freeze that commits it, the scratchpad git never sees, the links the driver makes itself, the
# dirt a refusal reports, and the diary a resumed or finished run leaves behind.

# Freeze whatever the process left behind so the next process starts from a committed tree.
# Returns 0 if something was actually frozen. This is the ONE freeze, and every path that ends a
# run reaches it: the four callers below, and the guard's `cut_run` through the `freeze`
# subcommand (#482). The guard used to keep a `git add -u` of its own here, so a run a tick cut was
# frozen without the untracked half #417 added -- #457's cut carried one modified file and left the
# two new ones, some 900 lines, untracked behind their own freeze commit.
# The diary is the one path this never stages, whatever the reason (#407): a freeze that swept it
# in published it inside a `WIP: cut by guard` commit, and its uncommitted lines are the dirty
# signal `start`/`resume`/`branch` read. The lines stay in the worktree either way.
freeze_uncommitted_work() {
  local reason=$1 untracked_pathspec=(. ":!$DIARY") swept=() swept_note="" path
  # Scratch is never the stage's work (#86): hidden first, so the sweep below cannot take it --
  # also on a worktree whose run was launched before `start` began hiding it.
  hide_scratchpad_from_git
  git -C "$worktree" add -u -- . ":!$DIARY"
  # The exclusion above governs what THIS call adds, not what is already in the index: a worker
  # that staged the diary by hand before it was cut put it there itself. `reset -- <path>` moves
  # the index entry and nothing else, so it is not the destructive reset the RULES forbid.
  git -C "$worktree" reset -q HEAD -- "$DIARY" 2>/dev/null || true
  # A FILE THE STAGE NEVER ADDED IS THE STAGE'S WORK TOO (#417). `git add -u` reaches only paths
  # git already tracks, so a cut stage that had written a new file left it untracked -- dirty
  # behind its own freeze, which is the one state `resume` refuses: #416's stage 2 wrote two new
  # files, some 1,200 lines, the freeze took the four tracked ones, and the task then waited for a
  # human to commit by hand what the mechanism had just produced. Still never `git add -A`, which
  # has destroyed a symlink in this repo: the paths arrive one by one from `ls-files --others
  # --exclude-standard`, so what `.gitignore` or `.git/info/exclude` keeps out stays out, and the
  # listing is also what the commit body below names. The links this driver creates itself (#404,
  # `driver_linked_paths`) are dropped only while they hold a link -- the same narrowing
  # `uncommitted_work` reads, so the freeze can neither commit them nor leave behind the one
  # entry that refusal was taught to ignore.
  while IFS= read -r path; do untracked_pathspec+=(":!$path"); done < <(driver_linked_paths)
  while IFS= read -r -d '' path; do swept+=("$path"); done \
    < <(git -C "$worktree" ls-files --others --exclude-standard -z -- "${untracked_pathspec[@]}")
  if [ "${#swept[@]}" -gt 0 ]; then
    git -C "$worktree" add -- "${swept[@]}"
    swept_note="The freeze also added these files, which the stage left untracked:"
    swept_note+=$'\n'"$(printf '  %s\n' "${swept[@]}")"
  fi
  git -C "$worktree" diff --cached --quiet && return 1
  # The note is the commit's body: a reader of the branch has to be able to tell work the agent
  # committed from work a freeze swept in. The commit carries the `Node-Change` trailer the host's
  # CI asks of every commit that touches the product tree (`tracker/freeze_commit.py`).
  "$agent_python" -m agent_os.product.tracker.freeze_commit --worktree "$worktree" \
    --subject "$WIP_SUBJECT ($reason)" --body "$swept_note"
}

# SCRATCH IS INVISIBLE TO GIT IN EVERY WORKER WORKTREE (#86). `scratchpad/` is where the RULES send
# a worker's diary and intermediate results, and no commit may carry them (#407). Read as dirt, they
# refused `start`, `resume` and `branch` over a run's own leftovers, and every run state needed its
# own exemption (#18, #22, #75, #84) -- the next state not covered was the next deadlock, cleared
# only by a human editing `.git/info/exclude`. A `.gitignore` of `*` INSIDE the directory ignores
# everything there, itself included, in this worktree only: `info/exclude` would have done the same
# for every checkout sharing the repository, the host's main checkout and its human among them.
# Files git already tracks under `scratchpad/` still show as modified -- that is an edit of work,
# or the tracked diary of an old branch, which `drop_the_resumed_runs_diary` handles -- and a
# `.gitignore` there that git tracks is the host's own and is left alone.
hide_scratchpad_from_git() {
  local ignore_file="$worktree/${DIARY%/*}/.gitignore"
  git -C "$worktree" ls-files --error-unmatch -- "${DIARY%/*}/.gitignore" >/dev/null 2>&1 && return 0
  [ "$(cat "$ignore_file" 2>/dev/null)" = '*' ] && return 0
  mkdir -p "${ignore_file%/*}"
  printf '*\n' >"$ignore_file"
}

# THE PATHS THIS DRIVER LINKS INTO A WORKTREE ITSELF, and that are links right now: `.env`, which
# `launch_stage` links (#404), and every `project.worktree_links` entry `init` provisions -- `.venv`
# by default. A real file or directory at one of those paths is the worker's, so only a symlink
# counts. A host's `.gitignore` of `.venv/` (with the slash) ignores a directory and never a
# symlink, which git sees as a file: every new slot worktree showed `?? .venv`, and `branch` and
# `start` refused it as dirty (stage1i). Read by `uncommitted_work` and by the freeze, which must
# not commit the links either.
driver_linked_paths() {
  local linked
  { echo .env; "$agent_python" -m agent_os.lib worktree-links 2>/dev/null || true; } | sort -u \
    | while IFS= read -r linked; do
      [ ! -L "$worktree/$linked" ] || printf '%s\n' "$linked"
    done
}

# Uncommitted work in the worktree, at most the five entries a refusal prints -- WITHOUT the links
# this driver puts there itself (#404, `driver_linked_paths`). `launch_stage` links `$main/.env` into a worktree that
# has none, and the dirty check below read that link as untracked work: a relaunch was refused for
# the driver's own doing, and in a repository carrying no ignore rule for `.env` -- a test's
# temporary one, or any project that does not gitignore it -- it was refused every time. This
# repository does ignore it, which is why the real worktrees never showed the defect; the guarantee
# cannot rest on that, because the driver is project-agnostic and knows no `.gitignore` of its own.
#
# `uncommitted_work resume` also leaves out the diary of the run it continues, and only that (#22,
# #84): see `drop_the_resumed_runs_diary`. Every other caller still counts the diary as work.
uncommitted_work() {
  local mode=${1:-} entries linked
  entries=$(git -C "$worktree" status --porcelain)
  # Narrow on purpose: only a link's UNTRACKED entry, and only while the path holds a symlink,
  # which is the shape the driver's link has. A `.env` that is a real file, a tracked `.env` git
  # reports as modified or typechanged, the diary and every other path still count as work.
  # Filtered before the five entries are taken, so a link cannot crowd a real one out.
  while IFS= read -r linked; do
    entries=$(printf '%s\n' "$entries" | grep -v -x -F "?? $linked" || true)
  done < <(driver_linked_paths)
  if [ "$mode" = resume ]; then
    entries=$(printf '%s\n' "$entries" | drop_the_resumed_runs_diary)
  fi
  [ -n "$entries" ] || return 0
  printf '%s\n' "$entries" | head -5
}

# THE DIARY IS THE HISTORY OF THE RUN `resume` CONTINUES (#22, #84). The freeze never stages
# the diary (#407), so a run the guard cut leaves it in the worktree, and `resume` used to refuse
# every relaunch over the lines the very run it resumes had written. Since #86 an UNTRACKED diary
# is hidden with the rest of `scratchpad/` and never reaches this filter; what still does is the
# diary of a branch forked while the base tracked it, reported ` M`.
# #407's reading -- uncommitted diary lines mean live work -- does not hold here: `alive` has
# already answered no, and the freeze has committed everything else. So the `git status
# --porcelain` entries on stdin come back without the diary's when `.state` line 1 records one of
# the two endings `resume` continues from: `CUT_BY_GUARD` (`after=guard_cut`) and `DONE` (#84) --
# a run that opened its pull request and exited is exactly the one the planner resumes with the
# validator's request-changes review, and its work is committed just as a cut run's is. A run that
# never launched (`FAILED_LAUNCH`) or reached `open-pr` and blocked (`BLOCKED`) is not one to
# resume, and a `.state` recording no ending is a run the driver never saw end: over any of those
# the diary still counts. Dropped are the diary's own entries -- ` M` while git tracks
# it, `??` when something else in `scratchpad/` is tracked -- and the collapsed `?? scratchpad/`
# only while the diary is the one untracked file inside it. The file itself is never touched,
# unlike #18's archive: the monitor reads it and the resumed run appends to it.
drop_the_resumed_runs_diary() {
  local previous_state diary_dir inside entry
  previous_state=$([ -s "$statefile" ] && sed -n '1p' "$statefile" || true)
  case "${previous_state%% *}" in
    CUT_BY_GUARD | DONE) ;;
    *) cat; return 0 ;;
  esac
  diary_dir=${DIARY%/*}/
  inside=$(git -C "$worktree" status --porcelain --untracked-files=all -- "$diary_dir")
  while IFS= read -r entry; do
    case "$entry" in
      '' | " M $DIARY" | "?? $DIARY") continue ;;
      "?? $diary_dir") [ "$inside" = "?? $DIARY" ] && continue ;;
    esac
    printf '%s\n' "$entry"
  done
  return 0
}

# A FINISHED RUN'S SCRATCH IS NOT THE NEXT RUN'S DIRT (#18, #75). No commit carries the diary
# (#407), and the RULES send a worker's intermediate results to `scratchpad/` as well, so a run
# leaves untracked files there after it ends, and the next `branch`/`start` read them as work left
# behind: in a host with no ignore rule for the directory, a dispatch after a completed issue was
# refused -- over the diary alone (#18), or over an ad hoc script, a commit message draft and a
# `__pycache__/` with no diary at all (#75), a shape #18's "the diary is the ONE thing dirty" never
# matched. What tells a finished run from one that never reached its end is the driver's own
# `.state` line 1, not the files' existence and not a line the agent may or may not have typed:
# `DONE`, `CUT_BY_GUARD`, `FAILED_LAUNCH` and `BLOCKED` are the endings
# (`agent_os.guard.RUN_ENDED_STATES`). Only then, only while nothing is alive, and only when git
# reports nothing dirty outside the diary's directory -- a refusal over anything else, a tracked
# file there included (a committed deliverable someone edited), still moves nothing -- the files go
# to `$cache/diaries/`, archived rather than deleted: the diary as `<run>.progress.log`, #18's
# name, and the rest under `<run>.scratchpad/` with their paths kept. Since #86 the directory is
# hidden from git and its files are no longer what refuses a dispatch; the archive stays so that
# each run starts on an empty scratchpad, and it takes every untracked file there, ignored or not,
# except the ignore file itself. A diary git tracks (a branch forked before the base stopped
# tracking it) is not untracked, so it is left alone: moving it would leave a deletion behind.
retire_finished_runs_scratchpad() {
  local previous_state entry scratch_dir run_name path destination
  local leftovers=()
  alive && return 0
  previous_state=$([ -s "$statefile" ] && sed -n '1p' "$statefile" || true)
  case "${previous_state%% *}" in DONE | CUT_BY_GUARD | FAILED_LAUNCH | BLOCKED) ;; *) return 0 ;; esac
  scratch_dir=${DIARY%/*}/
  # `-z`: every entry is `XY <path>` verbatim, never quoted. Anything git still reports -- the
  # scratch itself is hidden (#86), and an untracked path under it is tolerated only for a caller
  # that has not hidden it -- leaves the tree alone, the driver's own `.env` link aside (#404).
  while IFS= read -r -d '' entry; do
    [ "$entry" = '?? .env' ] && [ -L "$worktree/.env" ] && continue
    case "$entry" in
      "?? $scratch_dir"?*) ;;
      *) return 0 ;;
    esac
  done < <(git -C "$worktree" status --porcelain -z --untracked-files=all)
  # The candidates are every untracked file under the directory, ignored ones included -- which
  # since #86 is all of them. The ignore file that hides them stays, to keep hiding the next run's.
  while IFS= read -r -d '' path; do
    [ "$path" = "${scratch_dir}.gitignore" ] && continue
    leftovers+=("$path")
  done < <(git -C "$worktree" ls-files --others -z -- "$scratch_dir")
  [ "${#leftovers[@]}" -gt 0 ] || return 0
  mkdir -p "$cache/diaries"
  run_name="worker_$slot_key-issue$(cat "$issuefile" 2>/dev/null || echo unknown)-$(date +%Y%m%d-%H%M%S)"
  for path in "${leftovers[@]}"; do
    if [ "$path" = "$DIARY" ]; then
      destination="$cache/diaries/$run_name.progress.log"
    else
      destination="$cache/diaries/$run_name.scratchpad/${path#"$scratch_dir"}"
      mkdir -p "${destination%/*}"
    fi
    mv "$worktree/$path" "$destination"
  done
  echo "moved the finished run's ${#leftovers[@]} untracked $scratch_dir file(s) (${previous_state%% *}) to $cache/diaries/$run_name.*"
}
