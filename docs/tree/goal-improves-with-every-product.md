---
id: goal-improves-with-every-product
type: goal
title: Agentos improves with every product
sources:
- 'Owner design discussion of 2026-10-06: what Agentos is and what it is for'
- Owner design discussion of 2026-10-05/06 on Agentos's global goals, points 2, 3, 5, 6, 8; extends docs/AGENTOS_V2_PLAN.md
- 'Owner''s diagnosis of 2026-10-06: soundmax v1 was stopped for drift; its features needed an agentic engine that looks further ahead, and the agent building it lacked the tools to build software at the level of its requirements'
- 'Owner, 2026-10-09: «tenemos que optimizar el sistema agentos debe tener un objetivo global de eficiencia vinculado con la automejora»; the linked goal is goal-efficient-with-what-it-spends'
decisions:
- dec-one-owner-for-now
- dec-the-cycle-applies-at-every-scale
verification:
- judge: 'Recurrence of failures already recorded: tends to zero.'
- judge: 'Cost per verified checkpoint: falls from one method version to the next.'
- judge: 'Share of new nodes that reuse existing components: grows.'
- judge: 'Once a second product exists: it costs less than the first.'
---
What Agentos learns while building one product makes the next one cost less: it does not
forget, it looks for what it does not know, it knows how far to trust itself, it improves
its own method from evidence, and it turns what recurs into reusable pieces.

This goal is linked to goal-efficient-with-what-it-spends: what the method learns is judged, among
other things, by how much less it costs to verify a checkpoint, and that cost is the headline
measure of the efficiency goal, which breaks it into the parts a method change can move. The two
are read together, per method version.

Evaluators: in `verification`, set by the owner on 2026-10-06 -- trends until the vector gives the first measurements, numeric thresholds after.
