---
id: fr-a-usable-product-exists-early
type: functional-requirement
title: A usable product exists early
parent: goal-product-early-grown-by-use
sources:
- Owner design discussion of 2026-10-05/06 on Agentos's global goals, point 1; extends docs/AGENTOS_V2_PLAN.md
decisions:
- dec-puntales-run-as-headless-processes
- dec-a-puntal-plans-in-one-turn-and-code-executes
- dec-tests-harden-they-do-not-build
- dec-top-down-acceptance-is-essential-even-when-judged
mechanism: |-
  Stage 1. The owner writes the product's goals and their evaluators; the expert populates small
  requirement and use-case nodes and records its questions, which reach the owner in a question
  session. Foundations -- persistence, identity, UI skeleton, and the means to deploy the app
  locally, run its tests and log from minute zero -- are built first as normal tickets, with the
  branch's essential acceptance and the owner's acceptance in the first test session; their tests
  come later. The shell goes live once the foundations are implemented and accepted; every other
  action is served by a puntal, and an action whose what is still in doubt by its schematic default.
---
A product the owner can use exists very early, even while most of what it does is
improvised. Nothing waits for a complete specification.
