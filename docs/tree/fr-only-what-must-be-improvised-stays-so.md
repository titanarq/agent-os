---
id: fr-only-what-must-be-improvised-stays-so
type: functional-requirement
title: Only what must be improvised stays so
parent: goal-product-early-grown-by-use
sources:
- Owner design discussion of 2026-10-05/06 on Agentos's global goals, point 1; extends docs/AGENTOS_V2_PLAN.md
decisions:
- dec-what-must-stay-a-model-call-is-hardened-by-evaluation
mechanism: |-
  Stage 2. A part that must stay a model call is hardened as llm_by_design, verified by an
  evaluation over accepted examples with a threshold; the determinism ratio (share of use served
  by deterministic code) measures the trend.
---
The product tends to determinism: in the end only what genuinely needs a language model
keeps one, on purpose and evaluated, and everything else is ordinary code.
