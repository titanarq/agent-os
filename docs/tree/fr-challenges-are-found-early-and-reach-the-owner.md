---
id: fr-challenges-are-found-early-and-reach-the-owner
type: functional-requirement
title: Challenges are found early and reach the owner
parent: goal-faithful-to-the-owners-goals
sources:
- 'The owner''s original proposal of 2026-10-04 (design discussion that produced docs/AGENTOS_V2_PLAN.md): ''risk reduction'' among its fundamental objectives, the challenge flag, escalation to level 0, the reliability metric'
- Final cross-check of the how pass, approved by the owner on 2026-10-06
decisions:
- dec-a-challenge-is-flagged-early-and-the-owner-decides
mechanism: |-
  Stages 1-2. A node is flagged as a challenge when a spike finds no solution or stays inconclusive
  past its timebox, when no verification can be written for it (neither a command nor a judged
  criterion), or when its cost -- time or spend -- exceeds what its goal accepts. A challenge blocks the
  hardening of what depends on it and reaches the next question session, where the owner redefines
  the goals or stops the work; the custodian may recommend stopping a branch, with its evidence. The
  finishing reliability -- the share of use cases hard to test against easy to test -- is shown per
  branch on the progress board.
---
Whether the product can be finished, with guarantees, is known as early as possible: a use case with
no known solution, no way to test it, or a cost its goal does not accept is found early and reaches
the owner, who redefines the goals or stops the work. How likely the product is to finish well is
visible all along.
