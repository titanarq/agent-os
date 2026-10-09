#!/usr/bin/env bash
# What `worker_task.sh <backend> init` does when the worker's worktree is absent. Sourced by the
# driver; it needs `agent_provision_worktree` and `agent_os_link_mechanism_venv` from
# `agent_task.sh`, and defining the functions runs nothing.

# Creates `worktree` on `init_branch` at the tip of `base`, reusing the branch when it survived a
# worktree that did not (deleted by hand, a disk wiped, a clone moved): `git worktree add -b` dies
# on "a branch named ... already exists" and leaves the operator to work out why. A branch is only
# reused when it holds nothing `base` lacks -- moving it to `base` then loses no work; one with
# commits of its own is left untouched and the message says how to keep or drop it.
# Returns 1, after saying why, when no worktree could be made.
agent_os_add_init_worktree() {
  local main=$1 worktree=$2 init_branch=$3 base=$4 holder own_commits
  # A worktree directory deleted by hand stays registered, and git then counts its branch as
  # checked out there: forgetting the registrations of directories that no longer exist comes first.
  git -C "$main" worktree prune
  if ! git -C "$main" show-ref --verify --quiet "refs/heads/$init_branch"; then
    git -C "$main" worktree add -q -b "$init_branch" "$worktree" "$base" \
      || { echo "git worktree add failed for $worktree"; return 1; }
    return 0
  fi
  holder=$(git -C "$main" worktree list --porcelain \
    | awk -v branch="refs/heads/$init_branch" '/^worktree /{path=substr($0, 10)} $1=="branch" && $2==branch{print path}')
  if [ -n "$holder" ]; then
    echo "init: branch $init_branch is already checked out at $holder, and git lets a branch be in"
    echo "  one worktree only. Use that worktree, or run: git -C $main worktree remove $holder"
    return 1
  fi
  own_commits=$(git -C "$main" rev-list --count "$base..$init_branch")
  if [ "$own_commits" -gt 0 ]; then
    echo "init: branch $init_branch survived without its worktree and holds $own_commits commit(s) that"
    echo "  $base does not have, so it is left as it is. To keep that work:"
    echo "    git -C $main worktree add $worktree $init_branch"
    echo "  To drop it and start over from $base:"
    echo "    git -C $main branch -D $init_branch    # then run init again"
    return 1
  fi
  git -C "$main" worktree add -q -B "$init_branch" "$worktree" "$base" \
    || { echo "git worktree add failed for $worktree"; return 1; }
}

# The whole of `init` for an absent worktree: the remote's tip fetched from the MAIN checkout (there
# is no worktree yet to fetch from), the worktree on a fresh branch of it -- never `main` itself, a
# branch another worktree has checked out cannot be checked out twice -- and the host's provisioning.
# Returns 1, after saying why, when the worktree was not made or its provisioning failed.
agent_os_init_worktree() {
  local main=$1 worktree=$2 init_branch=$3
  git -C "$main" fetch -q origin main \
    || { echo "could not fetch origin/main -- refusing to init a worktree from a base nobody can name"; return 1; }
  agent_os_add_init_worktree "$main" "$worktree" "$init_branch" origin/main || return 1
  echo "created $worktree on $init_branch @ $(git -C "$worktree" rev-parse --short HEAD) (from origin/main)"
  # `git worktree add` brings tracked files only: the host's `project.worktree_links` and
  # `project.worktree_setup_command` make it runnable, through the same helper the one-shot roles'
  # throwaway worktree uses (agent-os#41). A tree whose provisioning failed is removed along with
  # its branch, so the next `init` starts from nothing instead of calling it initialized.
  if ! agent_provision_worktree "$main" "$worktree"; then
    git -C "$main" worktree remove --force "$worktree" >/dev/null 2>&1
    git -C "$main" branch -q -D "$init_branch" >/dev/null 2>&1
    echo "removed $worktree and $init_branch -- fix the provisioning and run init again"
    return 1
  fi
  agent_os_link_mechanism_venv "$worktree" "$main" only-if-ignored
}
