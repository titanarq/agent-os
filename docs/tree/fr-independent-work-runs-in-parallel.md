---
id: fr-independent-work-runs-in-parallel
type: functional-requirement
title: Independent work runs in parallel
parent: goal-product-early-grown-by-use
sources:
- 'Owner, 2026-10-09: ''Para agentos paralelizar debería ser un objetivo''. The owner chose to place it as a requirement under goal-product-early-grown-by-use, not as a fifth goal, and approved its four evaluators as trends (''ya iremos mejorando con el uso'')'
- 'Owner, 2026-10-09, seeing the control with two slots and three dispatchable tickets stopped: ''no veo que estés paralelizando mucho''; ''ponlo como una regla, no sé con qué disparador, pero lo suyo es que los que planifican las tareas se hagan esta pregunta que te he hecho y tú como controlador también tenerla en cuenta para verificar que se hace'' (the question: can more work run at once right now?)'
- 'Owner, 2026-10-09: ''vamos sin límite de quota; si nos quedamos sin quota se para, si hay quota se sigue'''
- 'Owner, 2026-10-09: ''ten en cuenta que cuando la web que estés haciendo funcione con puntales, necesitará muchos agentes y a lo mejor hay agentes trabajando en partes de la web que están desbloqueadas mientras tanto, no se deben limitar'''
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

  Whoever plans asks, every run. The planner on each of its runs, and the control that supervises it
  (the human or the agent in that seat), ask themselves whether more work can run at once right now,
  and `python -m agent_os.product.dispatch headroom` is the answer: read-only, it says for each ready
  issue of a v2 host whether the driver would start it now or what it waits for -- an open
  dependency, code shared with a running ticket or with one ahead of it, or only the cap -- through
  the same rules the start gate applies, not a copy of them. The planner starts every issue that
  could start, not one per event, until the driver refuses for the cap; what is left waiting only for
  the cap is written on its issue (`headroom: waits only for the cap`), the raw material of the
  fourth evaluator, and the control verifies that this is done. The cap is not a decision anyone
  takes per product: quota is the only limit, so nobody is paged or asked to raise it
  ('vamos sin límite de quota; si nos quedamos sin quota se para, si hay quota se sigue').

  Puntales and workers never limit each other. The puntales that serve a product's actions and the
  workers that build its unblocked parts run at once: the worker cap (`slots`,
  `planner.max_parallel_issues`) never counts or delays a puntal, and no puntal waits for another,
  because each action is one headless process of its own (dec-puntales-run-as-headless-processes).
  The only thing they share is the account's quota.
implementation: '`agent_os/product/dispatch/` (rules.py, touched_code.py, the start gate), `agent_os/product/dispatch/headroom/` (the question every planning run asks), `prompts/planner.md` (EVERY RUN, ASK YOURSELF), `tests/product/puntal/contract/test_puntal_never_asks_the_worker_cap.py` (a puntal never reads the worker cap), `bin/worker_task.sh` (slots, the cap), `planner.max_parallel_issues` and `project.backends.<name>.slots` in `config/agents.yaml`, `docs/adr/2026-09-26-a-backend-runs-several-workers-in-slots-of-its-own.md`, `docs/adr/2026-09-15-parallelism-is-a-configured-cap-enforced-by-the-driver.md`. Nothing measures the four evaluators yet: they wait for the vector, and the planner''s `headroom: waits only for the cap` comments are what the fourth will count.'
state: implemented
---
Agentos does at the same time whatever does not depend on anything else, so the owner waits for the
longest piece of a wave and not for the sum of all of them. Parallel work never collides: what shares
code or order is sequenced before it starts, not reconciled afterwards.

Evaluators: in `verification`, set by the owner on 2026-10-09 -- trends until the vector gives the first
measurements, numeric thresholds after.
