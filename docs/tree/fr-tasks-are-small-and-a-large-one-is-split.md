---
id: fr-tasks-are-small-and-a-large-one-is-split
type: functional-requirement
title: Tasks are small, and a large one is split before it is dispatched
parent: goal-efficient-with-what-it-spends
sources:
- 'Owner, 2026-10-10, before attending a request in a test session («antes de antenderlo quiero que repases 3 puntos»), point 3: «Recucción de costes de agentos. Ahorro de tokens = reducción de contexto = reducción tamaño tareas»; «Evitar tareas grandes: dividirlas.»'
mechanism: pending
---
The size of a task decides the context its run carries and, with it, what the run costs: the owner
puts it as saving tokens being reducing context being reducing the size of tasks. So a task that is
large is divided into smaller ones before it is given to an agent, and the size of the tasks
dispatched is read as the measure of the saving (an evaluator proposed on
goal-efficient-with-what-it-spends). A smaller task is also what keeps a run within its context
ceiling (fr-an-agent-run-stays-within-a-bounded-context).

The substrate already splits some work: an issue is staged before dispatch and each stage runs in a
fresh process (docs/adr/2026-09-15-work-is-staged-before-dispatch-and-each-stage-runs-in-a-fresh-process.md),
and a split task is superseded by its children
(docs/adr/2026-09-24-a-split-task-is-superseded-by-its-children-and-closed-not-planned.md). What is
missing is a size at which a task must be split and who judges it; that is the mechanism, and it is
left to the first agent that builds it.
