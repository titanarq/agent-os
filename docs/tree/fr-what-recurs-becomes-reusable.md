---
id: fr-what-recurs-becomes-reusable
type: functional-requirement
title: What recurs becomes reusable
parent: goal-improves-with-every-product
sources:
- Owner design discussion of 2026-10-05/06 on Agentos's global goals, point 8; extends docs/AGENTOS_V2_PLAN.md
- 'Owner, 2026-10-10, before attending a request in a test session («antes de antenderlo quiero que repases 3 puntos»), point 3: «Ayudar a los agentes que hacen tareas repetitivas, como la captura de la telemetría con scripts o MCPs.»'
decisions:
- dec-a-component-has-a-core-and-extensions
mechanism: |-
  Stages 2-3. Components with a core and extensions, tested once, in the product's own package
  and promoted to a shared repository when another product reuses them; the expert copies by
  analogy before designing and explores wide and thin when there is no direct solution; schemas
  mined from improvised documents; compression measured by context per slice, new code per node
  and reuse.
---
Solutions that recur become named, tested pieces with a core and extensions, so each new
problem needs less new work and less context. The same holds for what the agents themselves do again
and again, such as capturing telemetry: a script or an MCP does it, so the agent that repeated it by
hand spends its context on the task (goal-efficient-with-what-it-spends).
