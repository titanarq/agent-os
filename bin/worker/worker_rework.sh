# shellcheck shell=bash
# Sourced by worker_task.sh. `resume --rework`: the step a run whose every stage is committed needs
# when the validator sends its pull request back with CHANGES_REQUESTED -- the one case `resume`
# refused with "nothing to launch". It appends the stage that carries the review's fixes to the
# issue's `## Stages` (`agent_os/product/tracker/rework.py` reads the review and writes the stage),
# and hands the review to the run as context. The driver then launches that stage like any other.

# Prepares the rework of issue `$1`: sets `extra_context` (the caller's, so the review comes first
# and a `--context` of the caller's after it) and updates the issue body when a stage is owed.
# Every refusal exits and writes nothing a plain `resume` would not: no state, pid or event.
prepare_rework() {
  local issue=$1 branch pull_requests body_out context_out stage_line review_context
  case "$issue" in ''|*[!0-9]*)
    echo "rework refused: no recorded issue for this worker (.cache/worker_$slot_key.issue)"; exit 1 ;;
  esac
  branch=$(git -C "$worktree" branch --show-current)
  [ -n "$branch" ] || { echo "rework refused: $worktree is on a detached HEAD"; exit 1; }
  resolve_stage_context "$issue" || { echo "rework refused: could not read issue #$issue"; exit 1; }

  pull_requests=$cache/worker_$slot_key.rework_pull_requests.json
  body_out=$cache/worker_$slot_key.rework_body.md
  context_out=$cache/worker_$slot_key.rework_context.md
  gh pr list --state open --head "$branch" --json number,reviews > "$pull_requests" \
    || { echo "rework refused: could not list the pull requests of $branch"; exit 1; }
  stage_line=$("$agent_python" -m agent_os.product.tracker.rework prepare \
    --pull-requests "$pull_requests" --issue-body "$bodyfile" --branch "$branch" \
    --stages-done "$stages_done" --stages-total "$stages_total" \
    --body-out "$body_out" --context-out "$context_out") || { echo "$stage_line"; exit 1; }
  echo "$stage_line"
  if [ -s "$body_out" ]; then
    "$agent_python" -m agent_os.issues update "$issue" --body-file "$body_out" >/dev/null \
      || { echo "rework refused: could not add the stage to issue #$issue"; exit 1; }
  fi
  review_context=$(cat "$context_out")
  extra_context="$review_context${extra_context:+

$extra_context}"
}
