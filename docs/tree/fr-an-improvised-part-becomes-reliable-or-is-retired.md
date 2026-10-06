---
id: fr-an-improvised-part-becomes-reliable-or-is-retired
type: functional-requirement
title: An improvised part becomes reliable, or is retired
parent: goal-product-early-grown-by-use
sources:
- Owner design discussion of 2026-10-05/06 on Agentos's global goals, points 1, 2; extends docs/AGENTOS_V2_PLAN.md
decisions:
- dec-tests-harden-they-do-not-build
- dec-retirement-is-a-relative-candidacy-the-owner-decides
- dec-the-cycle-applies-at-every-scale
mechanism: |-
  Stages 1-3. Improvised (a puntal; the owner's acceptance hardens the specification) -> implemented
  (deterministic code from the accepted specification, no tests first, held by the essential
  acceptance and the owner's use) -> hardened (tests from accepted interactions, coverage that only
  grows). A puntal's mechanical steps move into code helpers before the whole action. A part
  available and unused while its branch is used becomes a retirement candidate; the owner decides.
---
An improvised part becomes reliable as it proves its value. A part nobody uses is
retired, and its code goes with it.
