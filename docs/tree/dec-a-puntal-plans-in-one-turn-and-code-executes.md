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

**Implementation (#115, 2026-10-07).** `agent_os/product/puntal/` (a package; `fast/` holds the four
parts' shared shapes, `docs/AGENT_OS.md` §4.7 describes them):

1. *Pre-helper*: `fast/pre_helper.py`. The node declares what its action reads in its frontmatter,
   `reads:`, a list of read commands of the app's persistence API (`list tickets`,
   `get tickets {payload.id}`; `{payload.NAME}` is a field of the click's JSON payload). The tree
   schema carries the field (`agent_os/product/tree/models.py`, `Node.reads`) and the driver reads it
   tolerantly. A caller may add reads of its own (`--read`, or `reads` in the JSON request).
2. *The puntal*: one `claude -p` with no tool (`--tools=`), contract `prompts/puntal.md`; its response
   is the plan, `{"operations": [...], "answer": ...}`, with the shape and validation of
   `fast/operations.py` (`put`, `update`, `delete`, `allocate` with `{{name}}` placeholders).
3. *Executor*: the interface is `fast/executor.py` (the app's command reads the operations on stdin and
   prints `{"ok": ..., "bindings": ...}` or `{"ok": false, "errors": [...]}`); a refusal goes back for
   one retry turn. `fast/reference_executor.py` is a reference implementation and
   `bench/puntal/executor.py` applies it to the bench's JSON store.
4. *Post-helpers*: the response is released before the telemetry line (schema 2) and the `runs.tsv`
   row are written.

The slow path is the Phase 0 tool loop under `prompts/puntal_slow.md`, entered when the plan says
`needs_state`; the telemetry carries `path` and `slow_path_reason`. The owner's accept, reject or
retry is `puntal_task.sh feedback` (`.cache/puntal/feedback.jsonl`, keyed by `invocation_id`), and every
record carries its `versions` (`agent_os/product/records/versions.py`). A host's shell calls the whole
thing through one entry independent of its stack, `puntal_task.sh --json` (`json_api.py`).
Not measured yet: the first measurement is on the vector's real actions.

