---
id: fr-results-are-read-through-indexes-not-raw-output
type: functional-requirement
title: Results are read through indexes, not raw output
parent: goal-efficient-with-what-it-spends
sources:
- 'Owner, 2026-10-09: «estás consumiendo demasiado en algunas tareas […] evita que se generen ficheros muy grandes que sea costoso trabajar con ellos, usa mecanismos de almacenamiento de información con índices que permitan jerarquizar la información e ir al grano sin leer líneas que no dan más contexto si no que distorsionan»'
mechanism: pending
---
An agent reads the line that answers its question and not the log that contains it. What an agent
produces is stored with an index that ranks it by level, so whoever reads it goes to the one entry
it needs; output that is expensive to read is a defect of whoever generates it, because the lines
that add no context do not merely cost tokens, they distort the reading. How each producer writes
its index is the mechanism, and it is left to the first agent that builds it.
