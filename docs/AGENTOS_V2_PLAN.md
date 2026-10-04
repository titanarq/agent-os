# Agentos v2 — construction plan

**Status:** approved by the owner in the design discussion of 2026-10-04. This document is the
specification for the first construction phases; it will be superseded by the product tree once
the tree format proves itself (Phase 3).

## Philosophy shift

- **Tokens are spent freely; context is what is contained.** Cost and quality degrade with
  context size per call, not with the number of calls. Slices stay small, parallelism goes up.
- **The guard stays.** Ceilings and stall-cuts protect against loops (one issue once spent 49.5M
  tokens across ten stages, four of them reporting nothing), not against legitimate spend.
  Ceilings rise; the cut-on-stall mechanism is untouched.
- **v2 wraps v1, it does not rewrite it.** The execution substrate (guard, planner, workers,
  validator, refiner, tracker CLI) stays as the hands. The new subsystems grow inside this
  repository and reach hosts through the same `git subtree` channel.

## The three layers

1. **Execution substrate** (exists): dispatches, cuts, validates, refines, merges.
2. **Product layer** (new): a tree — global goals → functional requirements → use cases — stored
   as files in the *host's* repository; a decision ledger with challenge and friction mechanics;
   an expert role that populates the tree; a consolidator role; a level-0 goal-custodian role.
3. **Puntal layer** (new): the product's UI shell goes live early; every UI action is bound to a
   use case; an unimplemented action is answered live by a headless agent (a *puntal* — a shore
   that props the building up); usage telemetry drives which use cases get hardened into real
   code, displacing the puntal over time.

## Founding decisions (ledger seed)

These enter the ledger as its first entries, in the format Phase 1 implements. Each carries
premises and a review trigger so none of them ossifies. The ledger state machine is
`in-force → under-review → superseded-by`.

| # | Decision | Premises | Review trigger |
|---|---|---|---|
| 1 | v2 wraps v1 | The substrate's ADRs solve problems v2 will also have (identities, liveness, cuts, quota, edges-not-conditions) | The substrate blocks a v2 design for the third time |
| 2 | Tree as repo files, issues as generated dispatch tickets | Structured deep trees are unreadable and expensive in GitHub Issues; slice reads must be cheap and diffable | Tree slicing becomes the bottleneck, or a host needs concurrent non-git writers |
| 3 | Usage telemetry comes from one real human using the shell | Simulated usage measures the simulator's bias, not demand | A second real user exists |
| 4 | State real from day one, behavior improvisable | LLMs improvise behavior acceptably and consistent storage badly; a puntal without persistence contradicts itself between sessions | Phase 0 evidence contradicts it |
| 5 | Obey while challenging | Parallel workers relitigating decisions never converge; the missing piece is a cheap revocation channel, not disobedience | Challenge channel unused after 2 months, or friction telemetry never fires |
| 6 | Puntales run as headless Claude Code processes, same launch mechanism as workers | Reuses the driver plumbing (brief rendering, budget class, runs.tsv, stubbing discipline in tests) | Phase 0 go/no-go numbers |

Standing disciplines that ride along (not separate decisions, they instantiate the above):
**lazy materialization with write-back** — a node may declare `mechanism: pending`; the first
agent that needs it resolves it (spiking if needed) and writes it back into the node in the same
PR, never leaving it in a transcript; **difficulty is measured by timeboxed spikes, never by
self-reported estimates**; **order is a red check, not an exhortation** — schema violations and
orphan files fail the tree doctor the way host literals fail `test_no_host_literals.py`.

## Phase 0 — puntal spike (starts now; needs no vector project)

The riskiest hypothesis goes first. Deliverables:

- `puntal_task.sh`, a sibling of `worker_task.sh`: receives `{action, node slice (use-case
  description + ancestor goals), relevant persisted state}`, renders a short brief, launches the
  backend headless. Response returns to the app; everything is logged — action, node, latency,
  tokens, response. That log IS the telemetry the refiner will later consume.
- A toy test bench: 4–5 actions over a JSON document store. The puntal never writes code: it
  reads its slice, reads/writes state through the app's persistence API, and may leave a *gap
  note* ("asked for X, the node does not describe it") that feeds the refiner.
- A budget class `puntal`: small context, low per-invocation ceiling, its own `runs.tsv`.

**Measurement protocol.** Real `claude -p` invocations are authorized ONLY in the measurement
script, launched explicitly and never by pytest, with small briefs and a hard cap of ~30
invocations total. Pytest always stubs the backend binary (repository rule). Measure: p50/p95
full-response latency; time-to-first-signal with streaming; cost per action; coherence across 3
distinct sessions over the same persisted state.

**Go/no-go criteria (adjustable starting points):** first signal in UI < 5 s; full response
p95 < 30 s; mean cost < $0.10/action; zero contradictions over persisted state across sessions.
A no-go is a valid, valuable result: it must name which design alternative to try next (live
session per user-session instead of process-per-click, precomputation, batched puntales).

**Exit:** a PR with the bench plus `docs/spikes/2026-10-puntal-latency.md` reporting the numbers
against the criteria and a recommendation.

## Phase 1 — tree and ledger schemas, with their doctor (parallel with Phase 0)

A new module of the package, fully testable without network or real backend.

- **Node** (one file per node, Markdown with frontmatter): type (`goal` / `functional-requirement`
  / `use-case`), description, sources, solution mechanism (`pending` allowed), implementation
  pointer, **executable verification — mandatory for dispatch: a node without one escalates
  instead of dispatching**, state (`pending → improvised → hardened`), `foundation` flag, spike
  results, pointers to the decisions in force on it.
- **Decision**: premises, rejected alternatives, review trigger, state
  (`in-force → under-review → superseded-by`), accumulated friction.
- **CLI**: `validate`/`doctor` (orphan file or missing field = red check), `context <node>`
  (emits the slice: node + ancestor goals + decisions in force + sources), `compile` (generates
  dispatch-ticket issues from dispatchable nodes).
- The six founding decisions above are written as the first real ledger entries — if the format
  cannot hold them, the format is wrong.

**Exit:** the schemas survive Phase 3's real content load without daily rework.

## Phase 2 — wiring tree ↔ substrate

- `compile` creates dispatch issues carrying the node address; the worker's brief carries the
  slice, never the tree.
- Write-back discipline added to worker and refiner prompts.
- The validator validates against the node's verification (today: the issue's acceptance
  criteria; only the source changes).
- Challenge channel: a new issue type plus the obey-while-challenging rule; the validator logs
  friction against a decision's id when a constraint made the solution worse.
- Substrate changes are config, not code: ceilings up, `max_parallel_issues` up, optionally a
  worker class back on Claude.

## Phase 3 — vector host bootstrap

A new, deliberately tiny host project (the *vector*) adopts v2 via `agent-os-install`. The owner
writes its global goals (the lighthouse is theirs); a new **expert** role (prompt + class, in the
validator/refiner pattern) populates requirements and use cases, launching spikes where
feasibility is in doubt; `foundation` nodes (persistence, identity, UI skeleton) are built as
normal issues through the substrate. The shell does not go live until foundations are hardened.

## Phase 4 — shell live, hardening driven by use

Every action routes to real implementation or to a puntal; the owner uses the app; telemetry
(frequency, suffered latency, gap notes, errors) feeds the refiner, which prioritizes hardening
and compiles it to issues. The **consolidator** enters in its minimal version: it periodically
checks in-force decisions' premises against reality and distills telemetry into nodes. Schema
mining from improvised documents is its second iteration, not its first.

## Phase 5 — level 0 and metrics

The goal custodian audits deviation against the vector's goal tree, consumes friction and
challenges, and **recommends** (adjust a goal, abort a branch) with evidence attached — the human
publishes, with the refiner's graduation path (reviewed dry runs before running unattended).
Metrics fall out of the above: hardened/total per functional requirement, friction per decision,
spend per node (the per-feature spend gap the current mechanism has).

## Deliberately out, for now

Semantic memory engine (the consolidator starts as premise-checker and telemetry distiller),
schema mining, multi-user telemetry, autonomous abort by level 0, an MCP server for the tree
(the CLI slices cheaper; MCP comes when something external needs to look in).

## Dependencies and open items

- The vector project: chosen and its global goals written by the owner (pending).
- Phases 0 and 1 are independent of each other and of the vector; they start immediately on
  separate branches.
