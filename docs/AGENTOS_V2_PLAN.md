# Agentos v2 — construction plan

**Status:** approved by the owner in the design discussion of 2026-10-04; Phases 2-5 replaced by
Stages 0-3 on 2026-10-06, after the owner's discussion of Agentos's global goals. This document is
the specification for construction; what Agentos is for is the tree in `docs/tree/`, and this plan
will be superseded by that tree's mechanisms as they are written (Stage 1 on).

## Philosophy shift

- **Tokens are spent freely; context is what is contained.** Cost and quality degrade with
  context size per call, not with the number of calls. Slices stay small, parallelism goes up.
- **The guard stays.** Ceilings and stall-cuts protect against loops (one issue once spent 49.5M
  tokens across ten stages, four of them reporting nothing), not against legitimate spend.
  Ceilings rise; the cut-on-stall mechanism is untouched.
- **v2 wraps v1, it does not rewrite it.** The execution substrate (guard, planner, workers,
  validator, refiner, tracker CLI) stays as the hands. The new subsystems grow inside this
  repository and reach hosts through the same `git subtree` channel.
- **The cycle applies at every scale** (2026-10-06, `docs/tree/dec-the-cycle-applies-at-every-scale.md`):
  goal and use cases first, then agents that prop them up, then those agents turned into
  deterministic implementation, little by little -- for a product's use case, for a single action
  of a puntal, and for Agentos's own mechanisms. Hardening is not all or nothing.

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

## Phase 0 — puntal spike (done: #103)

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

## Phase 1 — tree and ledger schemas, with their doctor (done: #102)

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

## Status, 2026-10-06

- **Phase 0 done** (#103): `bin/puntal_task.sh`, the bench and `docs/spikes/2026-10-puntal-latency.md`
  -- no-go on time-to-first-signal (p95 8.6 s), go on full-response latency, cost and coherence.
- **Phase 1 done** (#102), changed after review: goals carry verification (tests run top-down from
  the goals), a node with children is a container, the slice shows the ancestors' verification.
- **What Agentos is for** (#104): the mission and Agentos's own tree in `docs/tree/` -- four goals
  with the owner's evaluators, seventeen functional requirements, six use cases, all
  `mechanism: pending`.
- The Phases 2-5 that followed here were written on 2026-10-04, before the owner's discussion of
  Agentos's global goals (2026-10-05/06), which added most of the pieces below. They are **replaced
  by Stages 0-3**. Everything they asked for is kept and placed in a stage (the challenge channel,
  the minimal consolidator and the metrics included); the last open item checks that nothing from
  either discussion was dropped.

## Stages (replace Phases 2-5)

A stage starts when the data it needs exists: building a computation before there is anything to
compute it from is the over-specification goal `goal-product-early-grown-by-use` rejects. One
exception, which is why Stage 1 records so much: **what must be recorded starts early even when
what is computed from it comes late** -- history that was not recorded is lost.

### Stage 0 -- the map (no product chosen, no mechanism)

Where every piece and every datum lives, in agent-os and in the vector: the map and the recording
conventions below, and the vector's layout. Nothing in this stage decides how a requirement is met.

### Stage 1 -- start the vector (no data yet)

Exit: the owner uses the product.

- The vector adopts v2 through `agent-os-install`: `agent_os/` as a subtree and `config/agents.yaml`;
  the stack is the product's.
- Substrate as config: Claude Code only (no Qwen class); Sonnet for every role except the custodian
  and the consolidator (Opus, minimal use); ceilings and `max_parallel_issues` up; more than one
  worker per backend through slots (#91).
- The owner writes the product's goals and their evaluators; the goals' tests come first and
  everything below is tested from them downwards.
- The **expert** role (Sonnet, prompt and class in the validator/refiner pattern) populates
  requirements and use cases as small nodes, launches spikes where feasibility is in doubt, writes
  the verification of `foundation` nodes before a worker touches them, and records its questions;
  a question goes to the expert before it goes to the owner.
- Foundations (persistence, identity, UI skeleton) are built as normal issues; the shell does not go
  live until they are hardened.
- `compile` creates the dispatch issues, each carrying its node address; the worker's brief carries
  the slice, never the tree; write-back discipline in the worker and refiner prompts; the validator
  validates against the node's verification, in a context separate from the worker's.
- The shell: every action routes to code or to a puntal; the owner's feedback on a puntal answer
  (accept, reject, retry) is recorded; a minimal test-session mode inside the app; the UI shows
  progress at once, and what counts as first signal is set per kind of action.
- The puntal's contract becomes `docs/tree/dec-a-puntal-plans-in-one-turn-and-code-executes.md`: a
  code pre-helper loads the state the node declares its action reads, the puntal plans in one model
  turn with no tools (operations and answer), a code executor applies the operations atomically
  through the app's API (which keeps derived data itself), post-helpers run off the critical path,
  and the slow path (a read the node did not declare) stays as the escape. `bin/puntal_task.sh` and
  `agent_os/puntal.py` change accordingly; the first real measurement is on the vector's actions.
- Minimal question sessions: one GitHub issue per session, opened by the owner
  (`docs/tree/dec-a-question-session-is-a-github-issue.md`).
- The tree format gains `experiments` (spike, demand probe, question with scope `what` or `how` and
  a default answer, lookup; outcome `open` allowed); an open `what` question blocks the hardening of
  its node, and its default stays schematic.
- The progress board: progress per branch, and the owner's order of the backlog, which weighs over
  the order use suggests.
- Recording from day one, by the conventions below.

### Stage 2 -- with use

Exit: branches with telemetry and hardened nodes.

- Hardening step by step: a mechanical step a puntal keeps doing moves into a code helper (a
  `component` of the app) before the whole action is hardened; the slow path's telemetry says
  which reads a node should declare.
- Hardening driven by use: `compile` emits hardening tickets for `improvised` nodes, in the order of
  use (frequency x the puntal's cost, latency and errors); verification extracted from interactions
  the owner accepted; `retired` for what nobody uses; `llm_by_design` for what must stay a model
  call, verified by an evaluation.
- Indicators: derived hardness (a soft product decision is revised by the refiner with a record, a
  hard one by the owner); unverified exposure per branch and its two triggers; definition degree per
  branch (the cap on demand probes); determinism ratio; iterations by cause; the slice size cap
  (`tree.max_slice_tokens`, red, answered by dividing the node); an episodic digest in the slice.
- Tests: selection per branch (integration tests on both sides); a coverage ratchet that never
  blocks use; mutation score as an indicator; a nightly full run as the safety net; `component`
  records with a core and `extends:`, nodes declaring `uses:`.
- Memory: telemetry a node, a test or a decision cites is copied into `evidence/`; uncited raw
  telemetry rotates after 90 days.
- Custodian (Opus), minimal: drift and rollback -- it decides whether a rollback needs the owner, and
  that discretion follows its record; a changed goal lists its descendants for the refiner; spend
  against use per branch.
- Consolidator (Opus), minimal: checks the premises of in-force decisions against reality and
  distills telemetry into nodes.
- Challenge channel: obey while challenging; friction is logged against a decision's id when a
  constraint made a solution worse.

### Stage 3 -- with history

- Accuracy per role and kind of judgment; autonomy earned by measured accuracy (cold start:
  reversible judgments autonomous from day one, irreversible ones to sessions until there is a
  record).
- Method learning: a method problem is one that recurs in two branches or more; a change of how is
  adopted with evidence (replay battery before, telemetry by method version after, automatic
  rollback on regression); a change that touches the what, or the evaluator, is the owner's;
  proposals are reviewed in question sessions; a successor model runs the battery once.
- Compression: named components, schemas mined from the documents puntales improvise, principles;
  the techniques (wide and thin, copy by analogy) in the expert; components promoted to a shared
  repository; mutation score as a hardening condition.
- Metrics: hardened/total per functional requirement, friction per decision, spend per node.

## The map

Where each piece lives. "Host" is the product's repository (the vector first).

| Piece | What it is for | Lives in | Stage |
|---|---|---|---|
| Product shell | Every action goes to code or to a puntal; test-session mode; records the owner's feedback | host, the app's own code (stack of the product) | 1 |
| Progress board | Progress per branch; the owner's order of the backlog | the host repository's GitHub Project | 1 |
| Test sessions | The owner tries a branch, accepts or rejects, answers the puntals' questions | inside the shell | 1 |
| Question sessions | Batches of `what` questions; reviews of the tree and of method proposals | one GitHub issue per session, in the host repository | 1 |
| Product tree | Goals, requirements, use cases, decisions, experiments, components | host `product/` (`tree.root`) | 1 |
| Agentos's own tree | Agentos's goals, requirements, use cases and decisions | agent-os `docs/tree/` | done |
| Components | Reusable pieces with a core and extensions | host `components/`, a package of its own; a shared repository in Stage 3 | 2 |
| Cited evidence | Telemetry records a node, a test or a decision cites | host `evidence/` | 2 |
| Raw telemetry | Puntal invocations, owner feedback, judgments and their outcomes | host `.cache/` (never versioned) | 1 |
| Tree CLI | Doctor, slice, compile; hardening tickets, slice cap, episodic digest | agent-os `agent_os/tree/` | 1-2 |
| Indicators | Hardness, exposure, definition degree, priority, determinism ratio, iterations, accuracy, compression | agent-os, a module of its own | 2-3 |
| Test selection and coverage | Per-branch selection, ratchet, mutation indicator, nightly run | agent-os (mechanism) and the host's CI | 2 |
| Expert | Populates the tree; experiments; foundations' verification | agent-os `prompts/`, class in host `config/agents.yaml` | 1 |
| Refiner | Grows and divides nodes; soft decisions; gap notes into experiments | same (exists) | 1-2 |
| Planner, worker, validator | Dispatch, harden, validate | same (exist) | 1 |
| Puntal | Serves what is improvised; gap notes | agent-os `bin/puntal_task.sh` (exists) | 1 |
| Custodian | Drift, rollback, spend against use | agent-os `prompts/`, class in host config | 2-3 |
| Consolidator | Premises, telemetry into nodes; later method proposals and compression | same | 2-3 |
| Guard | Loops and ceilings | agent-os (exists) | -- |

## Recording conventions (fixed in Stage 0, recorded from Stage 1)

The names and places are fixed now so nothing recorded in Stage 1 has to move; the schemas are
written in Stage 1.

| What | Where | Key |
|---|---|---|
| Changes to a node | a `Node-Change: usage \| rework \| owner` trailer on every commit that changes a file under the host's `product/`; the nodes are the files the commit touches | host git history |
| Puntal invocations | host `.cache/puntal/telemetry.jsonl` (exists, schema 1) | `invocation_id` |
| Owner feedback on a puntal answer (accept, reject, retry) | host `.cache/puntal/feedback.jsonl` | `invocation_id` |
| A judgment an agent took alone, and its later outcome | host `.cache/judgments/judgments.jsonl` and `.cache/judgments/outcomes.jsonl` | judgment id |
| Versions | every record carries the model, the CLI version and the method version (the agent-os subtree commit and the digest of the prompt that ran) | -- |
| Spend | `.cache/<role>/runs.tsv` and `.cache/spend/` (exist) | -- |
| Cited evidence | host `evidence/<YYYY-MM>/<record-id>.json`, copied when something cites it | record id |

## Deliberately out, for now

Semantic memory engine (the consolidator starts as premise-checker and telemetry distiller),
multi-user telemetry (`docs/tree/dec-one-owner-for-now.md`), autonomous abort of a branch by the
custodian (it recommends; the owner publishes), an MCP server for the tree (the CLI slices
cheaper; MCP comes when something external needs to look in). Schema mining is no longer out: it
is part of compression, in Stage 3.

## Dependencies and open items

- **The vector's product**: chosen and its goals written by the owner (pending).
  - **2026-10-06:** soundmax v2 was considered and set aside as too complex for a first vector (the
    owner's diagnosis of v1: its features needed an agentic engine that looks further ahead, and
    the agent building it lacked the tools to build software at the level of its requirements). A
    local skeleton exists under a provisional name, with an empty product tree, a components
    package and its selection criteria, which follow from Agentos's goals (`docs/tree/`): a UI the
    owner uses often, at least two functional branches, cheap executable verification, real
    persisted state from day one, a small first version, and actions that tolerate a few seconds
    of latency where they start improvised.
  - Reusable components start inside the vector, as a package of its own, and move to a shared
    repository when they are reused across products.
- **Doubts of the how pass**: all closed on 2026-10-06 -- the stages, the Phase 0 no-go
  (`docs/tree/dec-a-puntal-plans-in-one-turn-and-code-executes.md`) and where question sessions
  happen (`docs/tree/dec-a-question-session-is-a-github-issue.md`). Next: the mechanism of each
  requirement, goal by goal.
- **At the end of the how pass**: cross-check that no point was dropped -- first against the
  owner's review of the eight points of 2026-10-05/06 (which became the four goals of `docs/tree/`),
  then against this plan's own 2026-10-04 base, which that review extends (the owner's request,
  2026-10-06).
