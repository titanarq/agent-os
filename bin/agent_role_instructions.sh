#!/usr/bin/env bash
# SOURCED by bin/agent_task.sh: what each one-shot role is told first, and the two helpers only the
# EXPERT needs (the base its worktree is cut from, the directory its backend starts in). The
# contract itself -- the rules -- is a template under `prompts/`; this is the one line of
# instruction naming the run's own subject, kept out of the driver so adding a role does not grow it.

# `$1` role, `$2` subject (a number), `$3` the planner's context, or `(none)`. Prints the
# instruction, and RETURNS NON-ZERO for a role it has none for.
agent_role_instruction() {
  local role=$1 subject=$2 context=$3
  case "$role" in
  validator)
    printf '%s' "Validate pull request #$subject. Read AGENTS.md, then the issue it closes and
its parent (the brief the worker was given), then the diff; check every acceptance criterion and
every definition-of-done line; post exactly one review and then exit. Context from the planner: $context"
    ;;
  refiner)
    printf '%s' "Refine issue #$subject. Read AGENTS.md, then \`issues.py brief $subject\` for
the issue and its parent, then only the docs and paths they name. Decide whether it is one
reviewable task/bug (rewrite its body in place, after preserving the original as a comment) or a
feature/multi-piece issue (split into template-conformant sub-issues, each moved to status:refine,
then remove the original's own refine label). Validate everything you write, then post exactly one
summary comment starting with the marker <!-- refiner-summary -->. Context from the planner: $context"
    ;;
  expert)
    printf '%s' "Populate the product tree for issue #$subject. Read AGENTS.md, then \`issues.py brief
$subject\` for the issue and its parent, then the goals, evaluators and decisions of the tree, then
only what the request touches. Write small requirement and use-case nodes under the owner's goals
(never touch a goal or its evaluators), record experiments and questions with their scope and
default answer, settle every question of how yourself or by a spike, and flag challenges. Validate
the tree, commit with a Node-Change trailer, open one pull request, then post exactly one summary
comment starting with the marker <!-- expert-summary -->. Context from the planner: $context"
    ;;
  *) return 1 ;;
  esac
}

# The default branch of origin, fetched, as a commit: `origin/HEAD` when the clone knows it, else
# `main`. The expert writes a branch of its own, so it starts from the branch as origin has it NOW,
# resolved before its worktree is made. RETURNS NON-ZERO, warning on stderr, when origin cannot be
# reached or has no such branch: a run that cannot base itself on it gets no worktree at all.
agent_default_branch_ref() {
  local branch
  branch=$(git -C "$agent_main" symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null)
  branch=${branch#origin/}
  branch=${branch:-main}
  if ! git -C "$agent_main" fetch -q origin "$branch"; then
    echo "WARNING: cannot fetch origin/$branch -- no worktree, so this run cannot write a branch" >&2
    return 1
  fi
  git -C "$agent_main" rev-parse --verify -q "refs/remotes/origin/$branch"
}

# Where a role's backend starts: the main checkout, except the expert, which writes a branch and so
# starts in the worktree that branch lives in. `$1` role, `$2` that worktree (empty when none).
agent_backend_directory() {
  if [ "$1" = expert ] && [ -n "$2" ]; then printf '%s\n' "$2"; else pwd; fi
}
