---
id: fr-drift-is-caught-early-and-costs-at-most-one-step
type: functional-requirement
title: Drift is caught early and an error costs at most one step
parent: goal-faithful-to-the-owners-goals
sources:
- Owner design discussion of 2026-10-05/06 on Agentos's global goals, point 4; extends docs/AGENTOS_V2_PLAN.md
decisions:
- dec-drift-is-judged-at-every-step-and-audited-over-time
mechanism: |-
  Stages 1-3. Every pull request is judged against its branch's goals and use cases. Implemented and
  hardened nodes are checkpoints; agent-os-tree history <node> rebuilds a node's history from merges
  and Node-Change trailers, and a rollback returns to the last good checkpoint. The custodian audits
  periodically and decides whether a rollback needs the owner. Symptoms (rework that does not decay,
  high unverified exposure) trigger experiments. A successor model runs the method battery once; a
  CLI update gets the free flag check.
---
Progress is a chain of small verified steps, so a wrong turn is caught soon and undoing it
loses at most the last step. The product keeps going over months, across changes of
model and tools.
