---
id: dec-puntales-run-as-headless-processes
type: decision
title: Puntales run as headless Claude Code processes, same launch mechanism as workers
state: in-force
decided: 2026-10-04
sources:
  - "docs/AGENTOS_V2_PLAN.md, 'Founding decisions' row 6 and 'Phase 0'; approved by the owner in the design discussion of 2026-10-04"
premises:
  - "Reuses the driver plumbing (brief rendering, budget class, runs.tsv, stubbing discipline in tests)"
rejected_alternatives:
  - option: "A bespoke launch path for puntales, with plumbing of its own"
    reason: "Implied by the premise, which is the reuse of the worker driver's plumbing; not argued at approval, so no reason for rejecting it beyond that is on record"
    basis: implied
review_triggers:
  - "Phase 0 go/no-go numbers"
---
A puntal -- the headless agent that answers a UI action no real code implements yet -- runs as a
headless Claude Code process launched the way a worker is: through a driver that is a sibling of
`worker_task.sh`, with the same brief rendering, a budget class of its own, a `runs.tsv`, and the
same discipline of stubbing the backend binary in tests.

Held in reserve, NOT rejected: a live session per user session instead of a process per click,
precomputation, and batched puntales. The plan names them as the designs to try next if Phase 0's
go/no-go is no-go, so they are not listed under `rejected_alternatives`, which is what a worker
reads as "do not propose this again".

**Review trigger evaluated on 2026-10-06.** Phase 0 was a no-go on time-to-first-signal only (p95
8.6 s; full response, cost and coherence passed). The mechanism stays: the puntal is still a
headless Claude Code process. What changes is the work it is asked to do in that process --
`dec-a-puntal-plans-in-one-turn-and-code-executes`. The designs held in reserve stay in reserve.
