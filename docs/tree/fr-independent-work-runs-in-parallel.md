---
id: fr-independent-work-runs-in-parallel
type: functional-requirement
title: Independent work runs in parallel
parent: goal-product-early-grown-by-use
sources:
- 'Owner, 2026-10-09: ''Para agentos paralelizar debería ser un objetivo''. The owner chose to place it as a requirement under goal-product-early-grown-by-use, not as a fifth goal, and approved its four evaluators as trends (''ya iremos mejorando con el uso'')'
decisions:
- dec-dispatch-never-runs-two-tickets-on-the-same-code
verification:
- judge: 'Work items running at once when there is independent work: grows.'
- judge: 'A wave''s wall-clock time approaches that of its longest ticket, not the sum of its tickets.'
- judge: 'Merge conflicts between work done in parallel: few.'
- judge: 'No dispatchable work waits for another run to finish without a reason.'
mechanism: |-
  Stage 1, already in the substrate. A backend runs several workers at once in slots of its own
  (`project.backends.<name>.slots`, one worktree and one set of run files per slot), and
  `planner.max_parallel_issues` caps the workers alive across every slot of every backend; both
  default to one, so a host that wants parallelism raises them. The start gate
  (`python -m agent_os.product.dispatch start-gate`, called by `worker_task.sh start`) refuses, writing
  nothing, a ticket whose dependencies still have an open ticket or whose touched paths overlap those
  of a running ticket: what is independent starts together, and what shares code or order never does,
  so a conflict is prevented by ordering and never left to the merge
  (dec-dispatch-never-runs-two-tickets-on-the-same-code). The tickets `compile` renders carry the
  dependencies and touched paths that gate reads, so a wave is exactly the set of tickets with no open
  dependency and no overlap. What waits does so for a reason that is written down -- an open
  dependency, overlapping code, a shared `module:` label, the cap the host configured -- and never
  because another run happens to be unfinished.
implementation: '`agent_os/product/dispatch/` (rules.py, touched_code.py, the start gate), `bin/worker_task.sh` (slots, the cap), `planner.max_parallel_issues` and `project.backends.<name>.slots` in `config/agents.yaml`, `docs/adr/2026-09-26-a-backend-runs-several-workers-in-slots-of-its-own.md`, `docs/adr/2026-09-15-parallelism-is-a-configured-cap-enforced-by-the-driver.md`. Nothing measures the four evaluators yet: they wait for the vector.'
state: implemented
---
Agentos does at the same time whatever does not depend on anything else, so the owner waits for the
longest piece of a wave and not for the sum of all of them. Parallel work never collides: what shares
code or order is sequenced before it starts, not reconciled afterwards.

Evaluators: in `verification`, set by the owner on 2026-10-09 -- trends until the vector gives the first
measurements, numeric thresholds after.
