---
id: dec-a-puntal-plans-in-one-turn-and-code-executes
type: decision
title: A puntal plans in one model turn, and code helpers do everything else
state: in-force
decided: 2026-10-06
sources:
  - "Owner design discussion of 2026-10-06, doubt 2 of the how pass (what to do with the Phase 0 no-go)"
  - "docs/spikes/2026-10-puntal-latency.md and its raw data, docs/spikes/2026-10-puntal-latency-data/"
premises:
  - "The slowest action measured in Phase 0 took 8.4 s in five model turns of about 1.6 s each, and only one of them needed judgment"
  - "A call with no tool turn answered in 2.3 s, with its first text at 1.7 s"
  - "An LLM helper costs another model turn, so it is slower than code for persisting or deriving data"
rejected_alternatives:
  - option: "Measure the toy bench again with a coarser API"
    reason: "The measurement cap is spent and a toy only measures the toy; the next measurement is on the vector's real actions"
    basis: stated
  - option: "Language-model helpers for persistence and derived data"
    reason: "Each one adds a model turn of about 1.6 s on the critical path"
    basis: stated
  - option: "Keep the puntal as a tool loop over persistence primitives"
    reason: "It is what produced five turns where one carries judgment"
    basis: stated
review_triggers:
  - "On the vector's real actions, time-to-first-signal of the fast path exceeds the owner's criterion for that kind of action"
  - "Most calls of an action take the slow path"
---
A puntal answers a click in four parts:

1. **Pre-helper (code, before the model):** loads into the brief the state the action reads, as its
   node declares it (the expert writes that declaration), so the model spends no turn reading.
2. **The puntal (one model turn, no tools on the fast path):** decides what to do and returns it all
   at once -- the operations and the answer.
3. **Executor (code, on the critical path):** validates the operations and applies them atomically
   through the app's API, which offers whole operations and keeps derived data itself (derived data
   is never the puntal's job); it fills into the answer what only it knows, such as a new id. A
   validation error goes back to the puntal for one more turn.
4. **Post-helpers (off the critical path):** whatever the answer does not wait for -- gap notes,
   telemetry, and, where an action needs it, model helpers for judgment that is not urgent, in
   parallel.

The **slow path** stays as the escape: if the action needs state its node did not declare, the
puntal asks for it and pays one more turn, and the telemetry marks the case so the node is corrected
or the step hardened. The UI always shows progress at once; what counts as "first signal" is set per
kind of action with the vector's UI in front. Expected, not measured: about 2.5-3 s per click, first
text at about 1.7-2 s.

This contract is a how (`dec-the-cycle-applies-at-every-scale`): it changes with evidence, and the
mechanical steps a puntal keeps doing are, one by one, candidates to move into helpers.
`dec-puntales-run-as-headless-processes` stays in force -- a puntal is still a headless Claude Code
process; what changed is what it is asked to do in that process.
