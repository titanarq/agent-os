---
id: fr-ready-pull-requests-land-in-groups
type: functional-requirement
title: Ready pull requests land in groups under one CI, and one at a time when in doubt
parent: goal-efficient-with-what-it-spends
sources:
- 'Owner, 2026-10-11: «Agrupa PRs similares, para ello tendrás que tener a un agente que se encargue de ver qué commits merece la pena integrar y cuales no, esto es para agilizar, por tanto ante la duda, integrar de uno en uno»'
- 'Owner, 2026-10-11, asked whether this is for agentos itself: «Sí, para Agentos»'
decisions:
- dec-dispatch-never-runs-two-tickets-on-the-same-code
- dec-a-doubt-of-how-is-settled-by-an-experiment
verification:
- judge: 'Pull requests landed per CI run: grows.'
- judge: 'Minutes from a pull request''s approval to its merge: falls.'
- judge: 'Rounds returned to one at a time over rounds attempted: stays low.'
mechanism: |-
  The integrator, an agent in the merge seat, plans a round from the ready pull requests, judges
  which are worth integrating together and which are not, builds one integration branch from the
  group, lands it under a single CI run and records the round in a ledger. Whatever it doubts goes
  back to one at a time, the way it was done before. The design is the ADR below.
implementation: '`agent_os/product/integrator/` (plan, judge, build, result, landing and the rounds ledger), `bin/integrator_task.sh`, `prompts/integrator.md`, `docs/adr/2026-10-11-the-integrator-lands-a-group-of-ready-prs-under-one-ci-and-one-at-a-time-when-in-doubt.md`.'
state: implemented
---
Pull requests that are ready and alike are landed together under one CI run instead of one run
each, so the owner waits less and agentos pays for fewer repeated runs. An agent decides which
commits are worth integrating together and which are not; when it doubts, the pull request is
landed alone, because the point of grouping is speed and a doubtful group would cost more than it
saves.

Prevention of conflicts already exists (dec-dispatch-never-runs-two-tickets-on-the-same-code);
this requirement is the other side, what is ready and waiting to merge. What still conflicts is
fr-merge-work-is-not-reviewed-twice. Whether grouping pays is a doubt of how and is settled by the
measures of its evaluators, not by anyone's estimate (dec-a-doubt-of-how-is-settled-by-an-experiment).

Evaluators: in `verification`, as trends until the vector gives the first measurements.
