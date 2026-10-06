---
id: dec-a-challenge-is-flagged-early-and-the-owner-decides
type: decision
title: A challenge is flagged early, and the owner decides whether to go on
state: in-force
decided: '2026-10-06'
sources:
- The owner's original proposal of 2026-10-04 (design discussion that produced docs/AGENTOS_V2_PLAN.md)
- Final cross-check of the how pass, approved by the owner on 2026-10-06
premises:
- Knowing late that a product cannot be finished is the most expensive way to find out
- Whether to redefine a goal or to stop is a decision about what, so it is the owner's
- Difficulty is measured by timeboxed spikes, never by self-reported estimates (docs/AGENTOS_V2_PLAN.md, standing disciplines)
rejected_alternatives:
- option: The level-0 agents decide on their own whether the project is aborted
  reason: 'The approved plan keeps autonomous abort out: the custodian recommends with evidence and the owner publishes'
  basis: stated
- option: Experts estimate each use case's resolution time
  reason: Self-reported estimates are not measurements; a spike with a timebox is
  basis: stated
review_triggers:
- A product is found unfinishable after most of its work hardened
---
A node is flagged as a challenge when a spike finds no solution or stays inconclusive past its
timebox, when no verification can be written for it, or when its cost -- time or spend -- exceeds
what its goal accepts. A challenge blocks the hardening of what depends on it and goes to the next
question session; the owner redefines the goals or stops. A goal may carry the time it may take, and
the custodian measures deviation against it. The finishing reliability -- use cases hard to test
against easy to test -- is an indicator per branch.
