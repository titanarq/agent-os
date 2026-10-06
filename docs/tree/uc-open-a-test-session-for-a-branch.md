---
id: uc-open-a-test-session-for-a-branch
type: use-case
title: Open a test session for a branch
parent: fr-the-owner-is-asked-only-in-sessions-they-open
sources:
- 'Owner design discussion of 2026-10-06: what the owner does with Agentos (its use cases)'
decisions:
- dec-a-test-session-happens-inside-the-app
mechanism: |-
  Stage 1 (minimal). Inside the app: what changed since the last session, the cases to try ordered by
  exposure, the puntals' pending questions answered in context. Accepted interactions harden the
  specification; rejected ones return as rework or as questions of what; answers are written back.
---
The owner opens a test session for one branch or feature of the product: tries what changed
since the last session, accepts or rejects what it does, and answers the questions its
improvised parts have recorded. It is the only place where the product asks the owner
something in real time, and what the owner accepts there becomes part of how consolidated
parts are verified (fr-what-is-consolidated-is-correct).
