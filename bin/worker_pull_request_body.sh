#!/usr/bin/env bash
# The body of the pull request `worker_task.sh open-pr` opens. Sourced by the driver, which owns the
# variables read here (`backend`, `worktree`, `agent_python`, `issue_body`); defining the function
# runs nothing.
#
# `Closes #N` first, then what the validator needs that the issue cannot say: the files the branch
# changes outside the ticket's `touches` (`agent_os.product.tracker.paths_outside_touches`) -- listed
# and never refused, `docs/adr/2026-10-09-a-branch-outside-its-touches-is-listed-not-refused.md`. A
# listing that could not be made leaves the section out and says why on the driver's output.
pull_request_body() {
  local issue=$1 base_ref=$2 outside_touches_note
  outside_touches_note=$(printf '%s\n' "$issue_body" \
    | "$agent_python" -m agent_os.product.tracker.paths_outside_touches --worktree "$worktree" --base "$base_ref") \
    || outside_touches_note=""
  printf 'Closes #%s\n\nOpened by the %s worker at the end of its run, from %s. The acceptance criteria and\nthe definition of done are in the issue; a validator agent reviews this pull request against them,\nand merging stays a human act.\n' \
    "$issue" "$backend" "$worktree"
  [ -z "$outside_touches_note" ] || printf '\n%s\n' "$outside_touches_note"
}
