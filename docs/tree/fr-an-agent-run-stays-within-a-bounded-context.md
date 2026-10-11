---
id: fr-an-agent-run-stays-within-a-bounded-context
type: functional-requirement
title: An agent run stays within a bounded context
parent: goal-efficient-with-what-it-spends
sources:
- 'Owner, 2026-10-09: «recuerda no dejar que los subagentes lleguen a más de 150k de contexto, si es posible, pues el precio se incrementa mucho»'
- 'Owner, 2026-10-10, before attending a request in a test session («antes de antenderlo quiero que repases 3 puntos»), point 3: «Ahorro de tokens = reducción de contexto = reducción tamaño tareas»'
mechanism: pending
---
No agent carries more context than its task needs. The ceiling the owner set is 150K tokens, held
"si es posible": past it the price of every further turn grows, so a run that crosses it is a cost
to explain and to avoid, not a failure to hide. How the ceiling is read and kept is the mechanism,
and it is left to the first agent that builds it. What holds the context down is the size of the task: on
2026-10-10 the owner equated saving tokens with reducing context and with reducing the size of tasks,
so the ceiling is kept by dividing tasks (fr-tasks-are-small-and-a-large-one-is-split).
