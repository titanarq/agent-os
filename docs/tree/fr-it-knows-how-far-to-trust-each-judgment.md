---
id: fr-it-knows-how-far-to-trust-each-judgment
type: functional-requirement
title: It knows how far to trust each of its judgments
parent: goal-improves-with-every-product
sources:
- Owner design discussion of 2026-10-05/06 on Agentos's global goals, point 5; extends docs/AGENTOS_V2_PLAN.md
decisions:
- dec-a-method-change-is-judged-by-evidence-from-the-products
mechanism: |-
  Stages 1-3. Every judgment taken without the owner is recorded from day one with its later
  outcome, from outside: the owner's verdicts and reclaims, reverts, real spend, escaped defects.
  Accuracy per role and kind of judgment is computed in Stage 3, never self-reported; it feeds the
  validator's calibration (goal A), the custodian's discretion (goal B) and method learning.
---
Agentos measures how often each kind of its judgment turns out right, instead of asking
itself how sure it is.
