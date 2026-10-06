---
id: dec-v2-wraps-v1
type: decision
title: v2 wraps v1
state: in-force
decided: 2026-10-04
sources:
  - "docs/AGENTOS_V2_PLAN.md, 'Founding decisions' row 1 and 'Philosophy shift'; approved by the owner in the design discussion of 2026-10-04"
premises:
  - "The substrate's ADRs solve problems v2 will also have (identities, liveness, cuts, quota, edges-not-conditions)"
rejected_alternatives:
  - option: "Rewrite v1: a new execution substrate replacing the guard, planner, workers, validator, refiner and tracker CLI"
    reason: "The plan states that v2 does not rewrite v1, and the premise says why: the substrate's ADRs already solve identities, liveness, cuts, quota and edges-not-conditions, problems v2 will have as well, and a rewrite would solve them a second time"
    basis: stated
  - option: "Grow the new subsystems outside this repository, or deliver them to hosts by a channel other than the git subtree"
    reason: "Implied by the plan's sentence that the new subsystems grow inside this repository and reach hosts through the same subtree channel; not argued at approval, so no reason for rejecting it is on record"
    basis: implied
review_triggers:
  - "The substrate blocks a v2 design for the third time"
---
v2 wraps v1, it does not rewrite it. The execution substrate (guard, planner, workers, validator,
refiner, tracker CLI) stays as the hands: it dispatches, cuts, validates, refines and merges. The
new subsystems grow inside this repository and reach hosts through the same `git subtree` channel.
