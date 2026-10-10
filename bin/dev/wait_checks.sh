#!/usr/bin/env bash
# wait_checks.sh <repo-dir> <pr> [max_minutes=60] -- poll quietly until every check of the PR's CURRENT head concluded.
# Prints ONE line, "<pr> head=<sha7> <check>=<conclusion>,...", exit 0 all SUCCESS | 1 any other | 2 timeout.
# Use it instead of `gh pr checks --watch` or `gh run watch`, which reprint their table every few seconds.
set -uo pipefail
cd "$1" || exit 2; pull_request=$2; max_minutes=${3:-60}
for ((minute = 0; minute < max_minutes; minute++)); do
  line=$(gh pr view "$pull_request" --json headRefOid,statusCheckRollup -q \
    '"\(.headRefOid[0:7]) \([.statusCheckRollup[]|"\(.name)=\(.conclusion//"PENDING")"]|join(","))"' 2>/dev/null) || { sleep 60; continue; }
  checks=${line#* }
  if [ -n "$checks" ] && [[ "$checks" != *PENDING* ]] && [[ "$checks" != *"=,"* ]] && [[ "$checks" != *"=" ]]; then
    echo "$pull_request head=$line"
    [[ "$checks" =~ ^([^=,]+=SUCCESS,?)+$ ]] && exit 0 || exit 1
  fi
  sleep 60
done
echo "$pull_request TIMEOUT after ${max_minutes} min: ${line:-no data}"; exit 2
