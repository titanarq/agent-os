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
  - option: "A live session per user session instead of a process per click; precomputation; batched puntales"
    reason: "Not refuted: the plan names them as the designs to try next if Phase 0's go/no-go is no-go, and a process per click is what the spike measures first"
    basis: stated
review_triggers:
  - "Phase 0 go/no-go numbers"
---
A puntal -- the headless agent that answers a UI action no real code implements yet -- runs as a
headless Claude Code process launched the way a worker is: through a driver that is a sibling of
`worker_task.sh`, with the same brief rendering, a budget class of its own, a `runs.tsv`, and the
same discipline of stubbing the backend binary in tests.
