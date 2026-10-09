#!/usr/bin/env bash
# What `worker_task.sh status` prints about a run's events and spend. Sourced by the driver, which
# owns the variables read here (`events`, `issuefile`, `bodyfile`, `spenddir`, `backend`,
# `agent_python`) and `issue_total_tokens`; defining the functions runs nothing.

# The file `status` reads events from: the live log, or -- once `stage-exit` has archived the
# finished stage and emptied it -- this backend's newest archived stage of the recorded issue
# (the archive names sort by their UTC timestamp). Empty output when neither has events.
readable_events_file() {
  local issue newest
  if [ -s "$events" ]; then echo "$events"; return 0; fi
  issue=$(cat "$issuefile" 2>/dev/null || true)
  case "$issue" in ''|*[!0-9]*) return 0 ;; esac
  newest=$(ls -1 "$spenddir/$issue"/*-"$backend"-stage*.jsonl 2>/dev/null | sort | tail -1)
  [ -n "$newest" ] && [ -s "$newest" ] && echo "$newest"
  return 0
}

# Latest per-turn context size, cumulative output, turn count, session id -- read off the
# stream-json events. Delegates to agent_os.lib so there is exactly one implementation of
# "how big is a turn" / "did the run fail", shared with agent_os.guard's budget check.
# The context line is judged against the issue's OWN budget class, read off `$bodyfile` the same
# way `issue_token_line` below resolves `max_total_tokens` -- never the per-backend $max_context
# default, which read as a ceiling for every class alike and reported a healthy run as over budget
# (#483). The issue's own token total goes in under the per-stage context line, because the two
# are the same measure at the two scopes a run is judged at: `max_context` for this stage process,
# `max_total_tokens` for every stage the issue has taken (#387).
usage_report() {
  local report_events
  report_events=$(readable_events_file)
  [ -n "$report_events" ] || { echo "  (no events yet)"; return; }
  [ "$report_events" = "$events" ] ||
    echo "  (live log empty; showing the latest archived stage: ${report_events##*/})"
  "$agent_python" -m agent_os.lib usage-report "$report_events" "$bodyfile" |
    awk -v extra="$(issue_token_line)" \
      '{ print } extra != "" && /^  context/ { print extra; extra = "" }'
}

# The issue-wide line of that report, empty -- so the report shows only this stage's own numbers --
# when no issue is recorded, which is a run that was never staged. The ceiling is printed when the
# body on disk resolves to a class and left out when it does not: `start` has already refused a
# dispatch whose issue has no resolvable budget, and a report is not the place to relitigate that.
issue_token_line() {
  local issue ceiling
  issue=$(cat "$issuefile" 2>/dev/null || true)
  case "$issue" in
    ''|*[!0-9]*) return 0 ;;
  esac
  ceiling=""
  if [ -s "$bodyfile" ]; then
    ceiling=$("$agent_python" -m agent_os.lib resolve-budget \
      --field max_total_tokens < "$bodyfile" 2>/dev/null) || ceiling=""
  fi
  printf '  issue     %s tokens across every stage of #%s' \
    "$(issue_total_tokens "$issue")" "$issue"
  [ -n "$ceiling" ] && printf '  (ceiling %s)' "$ceiling"
  printf '\n'
}
