---
id: fr-it-seeks-what-it-does-not-know-before-building-on-it
type: functional-requirement
title: It seeks what it does not know before building on it
parent: goal-improves-with-every-product
sources:
- Owner design discussion of 2026-10-05/06 on Agentos's global goals, point 3; extends docs/AGENTOS_V2_PLAN.md
decisions:
- dec-an-assumption-is-tested-before-work-hardens-on-it
mechanism: |-
  Stages 1-2. Experiments recorded on their nodes (spike, demand probe, question, lookup; outcome
  open allowed). Unverified exposure triggers one at the edge of a hardening that would raise it,
  or on symptoms in the branch; the cheapest experiment first; demand probes capped per branch by
  its definition degree; foundations first.
implementation: 'The experiment record on a node (kind, scope, default answer, open outcome) and the not-hardenable property
  of an open `what` question: agent_os/product/tree/models.py, agent_os/product/tree/hardening.py (#113).
  Triggering experiments is not built.'
---
An assumption is tested before work is built on top of it, with the cheapest experiment
that can settle it.
