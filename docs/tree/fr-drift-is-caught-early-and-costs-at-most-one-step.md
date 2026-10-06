---
id: fr-drift-is-caught-early-and-costs-at-most-one-step
type: functional-requirement
title: Drift is caught early and an error costs at most one step
parent: goal-faithful-to-the-owners-goals
sources:
- Owner design discussion of 2026-10-05/06 on Agentos's global goals, point 4; extends docs/AGENTOS_V2_PLAN.md
mechanism: pending
---
Progress is a chain of small verified steps, so a wrong turn is caught soon and undoing it
loses at most the last step. The product keeps going over months, across changes of
model and tools.
