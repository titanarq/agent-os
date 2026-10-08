#!/usr/bin/env bash
# What `worker_task.sh open-pr` refuses to publish. Sourced by the driver, which owns the variables
# read here (`worktree`, `backend`, `agent_python`, `DIARY`) and `write_state`, `write_state_marker`
# and `project_value`; defining the functions runs nothing.
#
# Both refusals are for a branch whose work is finished and whose pull request would be wrong the
# moment it existed. Neither repairs anything: taking a file out of a commit already made, or
# rewording its message, is a rewrite, and `open-pr` rewrites nothing.

# NO COMMIT MAY CARRY THE DIARY (#407). `scratchpad/progress.log` is the monitor's input, not the
# task's output, and a branch that adds or modifies it publishes it: it reached `main` that way
# once, and from then on every worker pull request conflicted with `main` on it -- a conflicting
# pull request, which is the no-CI case #389 exists to prevent. Refused rather than repaired,
# because taking a file out of a commit already made is a rewrite and this step rewrites nothing:
# it names the commits so whoever picks the branch up knows what to take out. Called above the
# freeze and the merge on purpose -- a refused branch is left exactly as the worker left it, with
# nothing written to the worktree, to `.state` or to GitHub. The caller exits 0 with the other
# refusals: there is nothing to publish, which is not a failure of the run, and the exit hook still
# records its end. A branch whose diff DELETES the diary passes, which is how a branch forked before
# `main` stopped tracking it gets clean.
# Returns 0, after saying why, when the branch carries the diary.
branch_carries_the_diary() {
  local base_ref=$1 branch=$2 diary_in_diff diary_commits
  diary_in_diff=$(git -C "$worktree" diff --name-only --diff-filter=AM "$base_ref" HEAD -- "$DIARY")
  [ -n "$diary_in_diff" ] || return 1
  diary_commits=$(git -C "$worktree" log --format='  %h %s' --diff-filter=AM "$base_ref..HEAD" -- "$DIARY")
  echo "open-pr: $branch adds or modifies $DIARY against $base_ref -- no pull request."
  echo "  The diary is the monitor's input and no commit may carry it; these do:"
  if [ -n "$diary_commits" ]; then
    printf '%s\n' "$diary_commits"
  else
    echo "  (no single commit of the branch adds it: it came in through a merge)"
  fi
  echo "  Nothing was written: take $DIARY out of the branch and run open-pr again."
}

# THE NODE-CHANGE TRAILER IS JUDGED BEFORE THE PULL REQUEST EXISTS. A worker wrote `Node-Change:`,
# a blank line and `Co-Authored-By:`; git reads only the last paragraph as trailers, so the host's
# CI step (`agent-os-tree trailers`) found the trailer absent and the pull request was red from its
# first minute, with the validator and the planner already told it was ready. The same question is
# asked here, of the same commits, by `agent_os.product.tracker.branch_trailers`: silent and exit 0
# when the branch is sound or the host has no tree directory, one line per defective commit
# otherwise. Called AFTER the pre-merge freeze: a `WIP: cut by guard` commit that touches the tree
# is one more commit the pull request would carry, with no trailer.
# Prints the command's words; returns its status.
node_change_trailer_report() {
  "$agent_python" -m agent_os.product.tracker.branch_trailers --worktree "$worktree" --base "$1" 2>&1
}

# The ending for a branch the report above refused: the issue says why and goes to
# `blocked-on-human`, the state is `BLOCKED` so the exit hook records a cut and not a
# `worker_finished`, and the branch stays exactly as it is, unpushed -- the same ending as a
# rejected push, for the same reason: finished work with no pull request and no comment would sit
# in `doing` for nobody to see. Not handed back to the worker as another stage: a stage is a commit
# the issue's checklist names, `launch_stage` refuses an issue with every stage committed, and a
# worker may not rewrite a commit it already made, which is what a message in an EARLIER commit
# needs. TODO(#366): render from project.messages.
block_on_malformed_node_change_trailers() {
  local issue=$1 branch=$2 base_ref=$3 report=$4 note
  write_state "BLOCKED reason=malformed_node_change_trailer branch=$branch"
  echo "open-pr: the Node-Change trailers of $branch are not what the host's CI requires -- no pull request:"
  printf '%s\n' "$report" | sed 's/^/  /'
  echo "  Nothing was rewritten: reword the commits named above and run open-pr again."
  note="The work of this issue is committed on \`$branch\`, but its \`Node-Change\` trailers are not
what the host's CI requires, so no pull request was opened (it would have been red from its first
minute):

\`\`\`
$report
\`\`\`

This is \`agent-os-tree trailers --base $base_ref --agent-authored\` run in the worktree. Every
commit that touches the product tree ends with exactly one \`Node-Change: usage\` or
\`Node-Change: rework\` line (\`owner\` is the owner's own word and never a worker's) in the LAST
paragraph of its message, together with any \`Co-Authored-By:\` line and with no blank line between
them: git reads only that paragraph as trailers (\`git interpret-trailers --parse\` shows what it
sees).

What unblocks it: reword each commit named above (\`git commit --amend\` for the last one,
\`git rebase -i\` with \`reword\` for an earlier one), then run \`worker_task.sh $backend open-pr\`
again. The driver rewrites no commit."
  "$agent_python" -m agent_os.issues update "$issue" --comment "$note" \
    || echo "WARNING: could not comment the malformed trailers on #$issue"
  if "$agent_python" -m agent_os.issues move "$issue" blocked-on-human; then
    write_state_marker "$issue" "$(project_value labels.blocked_on_human)"
  else
    echo "WARNING: could not move #$issue to blocked-on-human"
  fi
}
