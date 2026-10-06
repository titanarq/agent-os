---
id: fr-what-is-consolidated-is-correct
type: functional-requirement
title: What is consolidated is correct, not just plausible
parent: goal-product-early-grown-by-use
sources:
- Owner design discussion of 2026-10-05/06 on Agentos's global goals, point 7; extends docs/AGENTOS_V2_PLAN.md
decisions:
- dec-top-down-acceptance-is-essential-even-when-judged
- dec-tests-harden-they-do-not-build
mechanism: |-
  Stages 1-3. The essential top-down acceptance always holds: an agent judges the branch against its
  goals and use cases (the validator on every pull request, the custodian periodically), calibrated
  against the owner's verdicts. Tests consolidate after use, from the most independent source
  available: the owner's acceptance, examples extracted from accepted interactions, tests by the
  expert, never the worker's alone. Per-branch test selection, a coverage ratchet that never blocks
  use, a nightly full run; mutation score an indicator in Stage 2, a hardening condition in Stage 3.
---
A consolidated part is verified by a source independent of whoever built it, with tests
shown to catch errors. Coverage grows with use and never blocks using the product.
