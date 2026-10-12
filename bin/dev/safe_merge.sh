#!/usr/bin/env bash
# safe_merge.sh <repo-dir> <pr> [--group <integration-pr> [--after <sha>]] -- merge with a merge commit ONLY if every check concluded SUCCESS and the head contains origin/main.
# Refuses on a pending, empty or non-SUCCESS conclusion, and merges pinned to the head it checked (--match-head-commit).
# --group: the member of a passed integration group (agent-os-integrate land). Every refusal stays except "head does not
# contain origin/main", replaced by: the integration head is green and contains the member's pinned head; origin/main is
# still the group's base or `--after` (the merge commit of the previous member); the member's head is the pinned one.
# The method is GROUP_MERGE_METHOD (merge|squash|rebase, default merge).
# Never squash without it: a host's `git subtree pull` needs the merge commit's metadata.
set -euo pipefail
cd "$1"; pull_request=$2; shift 2
integration_pull_request=""; expected_main=""
while [ $# -gt 0 ]; do
  case "$1" in
    --group) integration_pull_request=${2:?--group needs the integration PR}; shift 2 ;;
    --after) expected_main=${2:?--after needs a sha}; shift 2 ;;
    *) echo "REFUSED: unknown argument '$1'"; exit 1 ;;
  esac
done
[ -z "$expected_main" ] || [ -n "$integration_pull_request" ] || { echo "REFUSED: --after needs --group"; exit 1; }
git fetch -q
head_commit=$(gh pr view "$pull_request" --json headRefOid -q .headRefOid)
conclusions=$(gh pr view "$pull_request" --json statusCheckRollup -q '[.statusCheckRollup[]|.conclusion]|join(",")')
[ -n "$conclusions" ] || { echo "REFUSED: no checks"; exit 1; }
for conclusion in ${conclusions//,/ }; do [ "$conclusion" = SUCCESS ] || { echo "REFUSED: check conclusion '$conclusion' (all: $conclusions)"; exit 1; }; done
[ -z "$(echo "$conclusions" | grep -E '(^|,)(,|$)')" ] || { echo "REFUSED: empty conclusion in $conclusions"; exit 1; }
merge_flag=--merge
if [ -z "$integration_pull_request" ]; then
  git merge-base --is-ancestor origin/main "$head_commit" || { echo "REFUSED: head ${head_commit:0:7} does not contain origin/main"; exit 1; }
else
  integration_head=$(gh pr view "$integration_pull_request" --json headRefOid -q .headRefOid)
  integration_body=$(gh pr view "$integration_pull_request" --json body -q .body)
  integration_conclusions=$(gh pr view "$integration_pull_request" --json statusCheckRollup -q '[.statusCheckRollup[]|.conclusion]|join(",")')
  [ -n "$integration_conclusions" ] || { echo "REFUSED: integration #$integration_pull_request has no checks"; exit 1; }
  for conclusion in ${integration_conclusions//,/ }; do [ "$conclusion" = SUCCESS ] || { echo "REFUSED: integration #$integration_pull_request check conclusion '$conclusion'"; exit 1; }; done
  [ -z "$(echo "$integration_conclusions" | grep -E '(^|,)(,|$)')" ] || { echo "REFUSED: empty conclusion in integration checks $integration_conclusions"; exit 1; }
  pinned_head=$(echo "$integration_body" | sed -nE "s/^- #${pull_request} at \`([0-9a-f]+)\`\$/\1/p")
  [ -n "$pinned_head" ] || { echo "REFUSED: #$pull_request is not a member of integration #$integration_pull_request"; exit 1; }
  [ "$head_commit" = "$pinned_head" ] || { echo "REFUSED: head ${head_commit:0:7} is not the pinned ${pinned_head:0:7}"; exit 1; }
  git merge-base --is-ancestor "$pinned_head" "$integration_head" || { echo "REFUSED: integration head ${integration_head:0:7} does not contain the pinned head ${pinned_head:0:7}"; exit 1; }
  if [ -z "$expected_main" ]; then
    member_count=$(echo "$integration_body" | grep -cE '^- #[0-9]+ at `[0-9a-f]+`$')
    expected_main=$(git rev-parse "$integration_head~$member_count")
  fi
  [ "$(git rev-parse origin/main)" = "$(git rev-parse "$expected_main")" ] || { echo "REFUSED: origin/main moved, it is not ${expected_main:0:7}"; exit 1; }
  merge_flag=--${GROUP_MERGE_METHOD:-merge}
fi
gh pr merge "$pull_request" "$merge_flag" --match-head-commit "$head_commit"
echo "MERGED $pull_request at head ${head_commit:0:7}"
