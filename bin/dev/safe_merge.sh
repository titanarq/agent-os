#!/usr/bin/env bash
# safe_merge.sh <repo-dir> <pr> -- merge with a merge commit ONLY if every check concluded SUCCESS and the head contains origin/main.
# Refuses on a pending, empty or non-SUCCESS conclusion, and merges pinned to the head it checked (--match-head-commit).
# Never squash: a host's `git subtree pull` needs the merge commit's metadata.
set -euo pipefail
cd "$1"; pull_request=$2
git fetch -q
head_commit=$(gh pr view "$pull_request" --json headRefOid -q .headRefOid)
conclusions=$(gh pr view "$pull_request" --json statusCheckRollup -q '[.statusCheckRollup[]|.conclusion]|join(",")')
[ -n "$conclusions" ] || { echo "REFUSED: no checks"; exit 1; }
for conclusion in ${conclusions//,/ }; do [ "$conclusion" = SUCCESS ] || { echo "REFUSED: check conclusion '$conclusion' (all: $conclusions)"; exit 1; }; done
[ -z "$(echo "$conclusions" | grep -E '(^|,)(,|$)')" ] || { echo "REFUSED: empty conclusion in $conclusions"; exit 1; }
git merge-base --is-ancestor origin/main "$head_commit" || { echo "REFUSED: head ${head_commit:0:7} does not contain origin/main"; exit 1; }
gh pr merge "$pull_request" --merge --match-head-commit "$head_commit"
echo "MERGED $pull_request at head ${head_commit:0:7}"
