---
id: fr-agent-runs-are-measured-and-studied-to-compact-and-simplify
type: functional-requirement
title: Every agent run is measured, and the measurements are studied to compact and simplify
parent: goal-efficient-with-what-it-spends
sources:
- 'Owner, 2026-10-10, before attending a request in a test session («antes de antenderlo quiero que repases 3 puntos»), point 1: «Monitorizar los agentes.»'
- 'Owner, 2026-10-10, same three points, point 2: «A través de la monitorización de agentes: estudiar si se pueden compactar, reducir, eficientar no duplicando o simplificando.»'
decisions:
- dec-a-method-change-is-judged-by-evidence-from-the-products
mechanism: pending
---
What each agent run spends is recorded, and the records are studied to find where an agent can be
compacted, reduced or made more efficient by not duplicating what another already does or by
simplifying what it does. The study proposes; a change to how an agent works is a method change and
is judged by evidence from the products like any other
(dec-a-method-change-is-judged-by-evidence-from-the-products).

The substrate already measures the cost side: the tokens and dollars of every run and of every issue
are written per run under `.cache/spend/<issue>/` and read with `worker_task.sh <backend> status`
(docs/AGENT_OS.md, "Unit and who measures it"). What it does not yet do is read those records
across runs to say which agent, which instructions or which prompt repeat each other, so that part
is the mechanism and it is left to the first agent that builds it.
