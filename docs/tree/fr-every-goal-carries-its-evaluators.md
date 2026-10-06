---
id: fr-every-goal-carries-its-evaluators
type: functional-requirement
title: Every goal carries the evaluators that decide whether it is met
parent: goal-faithful-to-the-owners-goals
sources:
- Owner design discussion of 2026-10-05/06 on Agentos's global goals, point 7; extends docs/AGENTOS_V2_PLAN.md
decisions:
- dec-a-goal-without-evaluators-is-a-red-check
mechanism: |-
  Stage 1. A goal's verification holds its evaluators: commands, or criteria an agent judges; a goal
  without them fails the doctor. The owner writes them; they start as trends until there is data, and
  they run top-down: the slice of every node below a goal shows its evaluators.
---
A goal's evaluators -- its highest-level tests and its indicators -- come first, and
everything below is tested from them downwards. They are what ultimately watches over
the goal.
