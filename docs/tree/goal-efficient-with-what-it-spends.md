---
id: goal-efficient-with-what-it-spends
type: goal
title: Agentos is efficient with what it spends, and its self-improvement is what proves it
sources:
- 'Owner, 2026-10-09: «tenemos que optimizar el sistema agentos debe tener un objetivo global de eficiencia vinculado con la automejora»'
- 'Owner, 2026-10-09: «recuerda no dejar que los subagentes lleguen a más de 150k de contexto, si es posible, pues el precio se incrementa mucho»'
- 'Owner, 2026-10-09: «estás consumiendo demasiado en algunas tareas […] evita que se generen ficheros muy grandes que sea costoso trabajar con ellos, usa mecanismos de almacenamiento de información con índices que permitan jerarquizar la información e ir al grano sin leer líneas que no dan más contexto si no que distorsionan»'
- 'Owner, 2026-10-09: «no se deben limitar» (parallel work: the only limit is the quota; efficiency is therefore never less parallelism, see fr-independent-work-runs-in-parallel)'
decisions:
- dec-one-owner-for-now
- dec-a-method-change-is-judged-by-evidence-from-the-products
- dec-a-change-to-the-what-is-merged-only-on-the-owners-word
verification:
- judge: 'Cost per verified checkpoint, in dollars and in tokens: falls from one method version to the next.'
- judge: 'Spend on work done twice -- rework rounds, CI repeated because parallel merges invalidate it, relaunches of a run that was already paid for: tends to zero.'
- judge: 'Share of agent runs that go past the context ceiling: tends to zero, and agents read indexes, not raw output.'
- judge: 'Owner time per decision that reaches them: falls.'
- judge: 'Time from the owner''s word to the change merged: falls.'
---
Agentos delivers the same verified result with less of everything it spends: tokens and dollars,
work done twice, context carried by each agent and, above all, the owner's time, which is the
scarcest resource there is. Efficiency is waste per unit of verified work, never less work at once:
parallel work is limited by the quota and by nothing else
(fr-independent-work-runs-in-parallel).

This goal is linked to goal-improves-with-every-product, and the link runs both ways. Improving its
own method from evidence (fr-it-improves-its-method-from-evidence-of-use) is how efficiency rises,
and efficiency is what that improvement measures: the cost per verified checkpoint, an evaluator of
goal-improves-with-every-product, is the headline measure of this goal, read per method version
because every record carries the version (dec-a-method-change-is-judged-by-evidence-from-the-products).
The other evaluators here break that cost into the parts a method change can move.

The evaluators in `verification` are a proposal, written on 2026-10-10 from the owner's words
above: they are not the owner's until the owner signs them. Goals and evaluators are the owner's
alone to set or change (fr-only-the-owner-changes-a-goal-or-an-evaluator,
dec-a-change-to-the-what-is-merged-only-on-the-owners-word), and a goal without evaluators is a red
check (fr-every-goal-carries-its-evaluators, dec-a-goal-without-evaluators-is-a-red-check), so the
proposal stands in the field the check reads and waits for the signature before it merges.
Trends until the vector gives the first measurements, numeric thresholds after.
