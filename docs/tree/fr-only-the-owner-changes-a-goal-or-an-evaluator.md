---
id: fr-only-the-owner-changes-a-goal-or-an-evaluator
type: functional-requirement
title: Only the owner changes a goal or an evaluator
parent: goal-faithful-to-the-owners-goals
sources:
- Owner design discussion of 2026-10-05/06 on Agentos's global goals, points 4, 6; extends docs/AGENTOS_V2_PLAN.md
decisions:
- dec-a-change-to-the-what-is-merged-only-on-the-owners-word
mechanism: |-
  Stages 1-2. A pull request touching a goal or an evaluator is merged only on the owner's word: the
  owner's merge, or a question-session answer the validator checks it transcribes exactly. When a
  goal changes, agent-os-tree lists its descendants and the refiner reviews them.
---
Adding or changing a goal, or anything that decides whether a goal is met, is the owner's
decision; the change then reaches everything that hangs from it.
