---
id: fr-an-agent-run-stays-within-a-bounded-context
type: functional-requirement
title: An agent run stays within a bounded context
parent: goal-efficient-with-what-it-spends
sources:
- 'Owner, 2026-10-09: «recuerda no dejar que los subagentes lleguen a más de 150k de contexto, si es posible, pues el precio se incrementa mucho»'
mechanism: pending
---
No agent carries more context than its task needs. The ceiling the owner set is 150K tokens, held
"si es posible": past it the price of every further turn grows, so a run that crosses it is a cost
to explain and to avoid, not a failure to hide. How the ceiling is read and kept is the mechanism,
and it is left to the first agent that builds it.
