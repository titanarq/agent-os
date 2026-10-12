#!/usr/bin/env bash
# Which ticket `worker_task.sh open-pr` publishes for, and the pull request it opens or reuses.
# Sourced by the driver, which owns `pull_request_body` and `agent_python`; defining the
# functions runs nothing.

# THE TICKET BEING WORKED is the one the branch names (`<word>/<issue>-<slug>`): the slot's
# recorded issue can be a stale one from an earlier run (#230: `Closes #116` on the pull request
# of #138). A branch that names no ticket keeps the recorded issue. Prints the issue to use; the
# notice goes to stderr so it is not captured with it.
issue_the_branch_works_on() {
  local branch=$1 recorded_issue=$2 branch_issue
  branch_issue=$(printf '%s\n' "$branch" | sed -nE 's#^[a-z][a-z0-9-]*/([0-9]+)([-/].*)?$#\1#p')
  if [ -n "$branch_issue" ] && [ "$branch_issue" != "$recorded_issue" ]; then
    echo "open-pr: $branch names issue #$branch_issue but the slot recorded #$recorded_issue -- publishing for #$branch_issue" >&2
    echo "$branch_issue"
  else
    echo "$recorded_issue"
  fi
}

# The branch's open pull request, reused when there is one, else created. `gh pr list` can miss a
# pull request that exists (a listing that errored, a race with another publisher): `pr create`
# then refuses, and the branch's own pull request is the answer, not a failure (#230).
open_or_reuse_pull_request() {
  local issue=$1 branch=$2 base=$3 base_ref=$4 existing title
  existing=$(gh pr list --head "$branch" --state open --json number -q '.[0].number' 2>/dev/null || true)
  if [ -n "$existing" ]; then
    echo "open-pr: PR #$existing is already open for $branch"
    return 0
  fi
  title=$(gh issue view "$issue" --json title -q .title) || title="issue #$issue"
  if gh pr create --base "$base" --head "$branch" \
    --title "$title (#$issue)" \
    --body "$(pull_request_body "$issue" "$base_ref")"; then
    return 0
  fi
  existing=$(gh pr view "$branch" --json number,state -q 'select(.state == "OPEN") | .number' 2>/dev/null || true)
  if [ -n "$existing" ]; then
    echo "open-pr: PR #$existing is already open for $branch"
    return 0
  fi
  echo "open-pr: gh pr create failed -- the branch is pushed, the pull request is not"
  exit 0
}
