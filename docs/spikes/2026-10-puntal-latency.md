# Puntal spike: latency, cost and coherence of a process per click (Phase 0)

- Date: 2026-10-05 (measured), against `docs/AGENTOS_V2_PLAN.md` "Phase 0"
- Branch: `feat/v2-phase0-puntal-spike`
- Raw data: [`2026-10-puntal-latency-data/`](2026-10-puntal-latency-data/) (all 30 invocations)

## Verdict

**No-go on the plan's first-signal criterion as written; go on the other three.** The design — one
headless Claude Code process per UI action, state in a real store — is not refuted, but it is not
cleared to carry the live shell either. Three of the plan's four starting points hold with room to
spare, and the fourth fails by a factor of about 1.7 at p95 for a reason the data explains.

| Criterion (plan, "adjustable starting points") | Result | Verdict |
|---|---|---|
| First signal in UI < 5 s | p50 **5.77 s**, p95 **8.59 s** (n=24, first assistant text delta) | **FAIL** |
| Full response p95 < 30 s | p95 **8.69 s**, max 15.28 s (n=24) | PASS |
| Mean cost < $0.10 per action | mean **$0.0104**, max $0.0150 (n=24, notional) | PASS |
| Zero contradictions over persisted state across sessions | **0** in 24 invocations over 3 sessions | PASS |
| (added) the puntal ran only the persistence command | 0 violations, 0 permission denials | PASS |

A no-go has to name the design alternative to try next. It is at the end of this document: a
coarser persistence API, so that a mutating action costs one model turn instead of four. The data
below says why; it also says what that would **not** fix.

## What was measured

- **Driver and constraints.** `bin/puntal_task.sh` launching `claude -p` with `--safe-mode`,
  `--tools=Bash`, `--permission-mode dontAsk`, one allow rule (`Bash(./state *)`), a replaced system
  prompt, an empty scratch directory as cwd, `--no-session-persistence`, `--max-budget-usd 0.25` and
  streaming with partial messages. Model `claude-sonnet-5-5`, Claude Code 2.1.289, subscription
  login. Every call was a fresh process: no context is shared between invocations except through
  the persisted store.
- **Bench.** A ticket board over a JSON document store (`bench/puntal/`): five actions
  (`create_ticket`, `change_status`, `show_board`, `board_report`, `export_csv`), each bound to a
  node file. `export_csv` is bound to a node (`uc-3-see-the-board`) that does not describe it, on
  purpose, to exercise the gap note.
- **Spend, exactly 30 real invocations (the cap, enforced in code and counted before each call):**
  2 calibration, 24 main stage (3 sessions of 8, same store), 4 reserve probes on another model.
  Notional cost of the whole spike: $0.35.
- **Definitions.** Latencies run from the moment `puntal_task.sh` is entered (the click reaching
  the driver), so they include shell and Python start-up (mean 0.28 s). *First signal* is the first
  assistant **text** delta of any message, the earliest moment a UI could show content of the
  answer. `first_event` (the CLI's init line) and the first tool call are reported separately.
  `cost_usd` is the CLI's `total_cost_usd`, which under a subscription login is **notional**
  (API-equivalent), not money charged.
- **How the numbers were produced.** `measure.py summarize` over the raw files. I recomputed
  p50, p95 (nearest rank), means, maxima and the by-population split independently from the raw
  telemetry with a separate script, and the results match to the printed precision. The final store
  was also checked by hand: six tickets (five created in the main stage, one in the reserve),
  counter 6, and the stored summary matches the count per status.

## Results

### Latency has two populations, not one distribution

| Population | n | total p50 | total p95 | first text p50 | first text p95 | cost mean |
|---|---|---|---|---|---|---|
| Read-only actions (`show_board`, `board_report`, `export_csv`): 1 tool call | 10 | 4.38 s | 5.85 s | 4.28 s | 5.77 s | $0.0068 |
| Mutating actions (`create_ticket`, `change_status`): usually 4 tool calls | 14 | 7.28 s | 15.28 s | 7.18 s | 15.22 s | $0.0130 |

By number of tool calls: 12 invocations with one call took 4.45 s on average (3.60 to 5.85 s);
11 with four calls took 8.28 s (6.31 to 15.28 s). Each extra **sequential** tool call adds
about 1.0 to 1.3 s (the second figure counts the 15.28 s outlier, the first leaves it out), which
is one more model turn. The model's first tool call lands at p50 1.8 s (p95
2.6 s), and the CLI's first event at 0.75 s.

The pattern in the tool calls is the same every time: `create_ticket` is `next-id`, `put` the
ticket, `list` the tickets, `put` the recomputed summary. `change_status` is `get`, `update`,
`list`, `put summary`. The puntal derives and writes the summary itself, one command per turn,
because the persistence API offers only primitives.

**Consequence for the criterion.** The puntal reads state before it answers, so the first
*content* the user can see arrives after at least one tool round trip. Even the cheapest actions
sit at p50 4.3 s with p95 5.8 s: on this data a one-turn action would also miss "p95 < 5 s" by a
small margin. A text-only call with no tool at all (calibration, 1 sample) answered in 2.3 s with
first text at 1.7 s, which is the floor of the process itself.

Two readings of "first signal in UI" are possible. If the UI may show a progress indicator on the
first tool call (p95 2.6 s), the criterion passes trivially, but that signal carries no part of the
answer, and this report does not count it as a pass. The strict reading is the one in the table.

### The 15.3 s outlier

One `change_status` in session 1 took 15.28 s. Its tool calls landed at 1.8, 3.5 and 4.8 s, and the
fourth, the `put` of the recomputed summary, at 13.8 s: nine seconds for the model to emit one
command, with 292 output tokens in the whole call. The nature of that stall is not established (one
sample); it is the reason p95 for mutating actions is 15.2 s while the main-stage p95 is 8.7 s.

### Cost and context

Mean $0.0104 per action, maximum $0.0150, $0.25 for all 24. The prompt cache read fraction was 0.89;
the calls ran back to back, so the cache was warm. **A real shell with clicks minutes apart will
pay cache creation more often**; the one cold call (calibration, 3,245 tokens cache-created) cost
$0.0131 and showed no visible latency penalty, but that is one sample.

- Context floor (what a call carries before it does anything): **3,247 tokens** (cold, text only).
- Context peak per action: mean 4,122, **max 4,634**. Total tokens per action: p50 7,734, max 20,882.
- The `puntal` class placeholders (`max_context` 30,000, `$0.25`, 300,000 total tokens) are 6 to 14
  times above the largest value observed. They were not changed here because this is one model, one
  toy domain and 24 samples; a calibrated set belongs with the refiner's measurement of real usage.

### Coherence

24 invocations in 3 sessions over one persisted store, with the oracle being the bench's own
reference model of the rules: store invariants after each invocation, a one-step replay of each
action, the response against the store, and a ledger replayed from the empty store at each
session boundary. **No contradiction, no accepted invalid transition, no reused id.** The gap note
was left in 3 of 3 actions the node does not describe and in none of the others. Nothing was left in
the scratch directory.

The limits of that result are real: the domain is five actions and one summary document; the oracle
is the code that wrote the bench, not an independent party; and coherence of *improvised behavior*
(which this toy barely exercises, since the rules are small and written in the node) was not
stressed. It supports founding decision 4 for state; it does not show that a puntal improvising a
large behavior stays consistent.

### Reserve probe: Haiku 4.5 (n=4, not part of the verdict)

Spent on another model to ask whether a faster model is the lever. It was not, on this evidence:
mean 10.99 s total and $0.0204 per action against 6.27 s and $0.0104 for Sonnet 5.5. It also used
more turns (`create_ticket` made six tool calls, two of them malformed `put summary/board ...`
commands that it had to retry) and carried a larger first-turn context (about 5.2k tokens against
3.3k). The probe is confounded by a cold prompt cache for a second model and has n=4, so it
says "no sign that a smaller model helps here", not "Haiku is slower".

## Threats to validity

- One model, one machine, one network path, one day, a subscription login: latencies of another
  hour or account can differ.
- p95 over 24 samples is the 23rd value; a single slow call moves it (see the outlier).
- The read-only population (10) and the mutating one (14) are small and unevenly spread across
  sessions by design.
- Cost is notional. Warm prompt cache throughout.
- The oracle is the bench's own; the domain is a toy.
- **Known hole in the "never writes code" constraint.** Claude Code auto-approves read-only Bash
  commands (`cat`, `ls`) regardless of permission rules, so one could run before the stream audit
  cuts the run. In this run: 0 violations and 0 permission denials, and the audit would have
  recorded one. The hole would be closed by an MCP bridge as the single tool, which the driver's
  ADR explains `--safe-mode` rules out (it drops every non-SDK MCP server); that trade was taken
  deliberately to keep the user's own context out of each call.

## What did not go as planned

- The criterion that fails (first signal) is the one the plan put first.
- Three things about the real CLI could not be checked offline and were verified only in the
  calibration: `--tools=Bash`, the `Bash(./state *)` allow rule under `dontAsk` and `--safe-mode`
  with subscription auth all work (calibration records: `init.tools == ["Bash"]`, no MCP servers,
  no denials).
- The context ceiling of the class was a guess and turned out far too loose.

## Recommendation

**Do not put the shell live on a process-per-click puntal as it stands.** Keep the design (state
real, process per click, class and telemetry as built) and try the following, in this order,
before reconsidering the process model.

1. **Next alternative to try: a coarser persistence API.** Give the app commands that do a whole
   mutation atomically (`create-ticket`, `change-status`, which maintain the summary themselves),
   so that a mutating action is one tool round trip and the puntal does not re-derive and re-write
   a summary on every click. **Prediction, which can fail:** mutating actions fall to the read-only
   population (p50 about 4.4 s, p95 about 5.9 s) and mean cost to about $0.007. If they do not, the
   hypothesis that latency here is sequential model turns is wrong. Measure it with the same
   `measure.py` and a new 30-call cap, not with this one's leftover.
2. **Read-only actions should not be puntales for long.** `show_board`, `board_report` and
   `export_csv` are pure functions of state; they are the first actions the telemetry will ask to
   harden, which is the plan's design working as intended. Until then they are the cheap
   population: $0.0068 and about 4.4 s.
3. **Decide what "first signal" means for the UI** before the next measurement. If the owner accepts
   a progress marker on the first tool call (p95 2.6 s) as the signal, the criterion is met by a UI
   decision rather than a measurement; that is a legitimate decision but it is the owner's, and the
   report does not make it.
4. **A live session per user session is not supported by this data as the main lever.** It would
   remove the 0.75 s CLI start and part of the first turn, but the dominant cost is the number of
   sequential model turns, which a live session does not remove. That is an inference from the
   breakdown above, not a measurement; test it only after 1 to 3.

**Effect on the ledger.** Founding decision 6 (`dec-puntales-run-as-headless-processes`) names the
"Phase 0 go/no-go numbers" as its review trigger; a failed criterion arguably fires it. This
branch does not touch the ledger (it lives in the Phase 1 branch), and moving a decision to
`under-review` is the owner's call. Founding decision 4 (state real from day one) is **supported**
by the coherence result, with the limits above.

## Reproduce

```
.venv/bin/python bench/puntal/measure.py --workdir docs/spikes/2026-10-puntal-latency-data summarize
```

reproduces the summary from the raw telemetry and the oracle trace in this directory (paths were
replaced by `<repo>` and `<workdir>`; nothing else in the files was edited). A new measurement is
`bench/puntal/measure.py status | calibrate | main --session N | reserve | summarize` with
`--allow-real-calls`; the cap of 30 real invocations is a constant in the script and the count lives
in `~/.cache/agent-os/puntal-bench-real-calls.json`, so **this measurement has used all of it**: a
new one needs a deliberate change of `REAL_CALL_CAP` or of the counter file, which is a decision to
spend more.
