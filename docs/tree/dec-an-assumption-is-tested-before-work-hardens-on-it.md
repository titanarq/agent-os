---
id: dec-an-assumption-is-tested-before-work-hardens-on-it
type: decision
title: An assumption is tested before work hardens on it, cheapest experiment first
state: in-force
decided: '2026-10-06'
sources:
- Owner design discussion of 2026-10-06, how pass, level 3, goal D (Agentos improves with every product)
- Owner design discussion of 2026-10-05/06, point 3 (active information acquisition)
premises:
- Hardness grows with what depends on a thing, so the cheapest moment to find an assumption false is before anything hardens on it
- The owner's attention is the most expensive experiment
- 'Experiments are expensive: they should start when they become urgent, not from a reserved share of capacity'
rejected_alternatives:
- option: Reserve a fixed share of parallel slots for experiments
  reason: 'The owner: experiments are expensive; what matters is an indicator of when experimenting becomes urgent'
  basis: stated
- option: Test every assumption upfront
  reason: It would be the new over-specification; only assumptions that would lock work are tested before it hardens
  basis: stated
review_triggers:
- An assumption is refuted after work hardened on it
- Experiments delay the minimal product
---
Open assumptions are recorded on their nodes as experiments (spike, demand probe, question, lookup;
outcome `open` allowed). A node's unverified exposure is the number of implemented or hardened nodes
that depend on an open assumption -- the same count as hardness. An experiment is triggered when the
next hardening would raise that exposure, or by symptoms in the branch (rework that does not decay,
gap notes piling up, friction, puntal errors). The cheapest experiment that can settle it goes
first. Demand probes are capped per branch by its definition degree, not by a fixed number.
Foundations' assumptions come first, since everything depends on them.
