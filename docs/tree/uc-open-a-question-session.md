---
id: uc-open-a-question-session
type: use-case
title: Open a question session
parent: fr-the-owner-is-asked-only-in-sessions-they-open
sources:
- 'Owner design discussion of 2026-10-06: what the owner does with Agentos (its use cases)'
decisions:
- dec-a-question-session-is-a-github-issue
mechanism: |-
  Stage 1. One GitHub issue freezes the batch: questions of what, numbered, grouped by branch, ordered
  by what they block, each with its default; the digest of what was decided without the owner; tree
  reviews (goals, spend against value), method proposals that touch the what, rollbacks the custodian
  escalated, retirement candidates. The reply wakes the planner; the pull request that writes it back
  is merged on the owner's word, which the answer is.
---
The owner opens a question session: answers the doubts about what that have been recorded,
reviews the tree (its goals, and spend against value per branch), the proposals to change
Agentos's method that touch the what, and any undoing of work that Agentos chose to bring to
the owner instead of deciding it alone.
