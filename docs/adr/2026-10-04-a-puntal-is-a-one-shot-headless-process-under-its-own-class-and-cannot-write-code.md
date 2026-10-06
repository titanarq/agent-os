# A puntal is a one-shot headless process under its own class, and it cannot write code

- Date: 2026-10-04
- Status: accepted (a spike: the numbers decide whether it stays, `docs/spikes/2026-10-puntal-latency.md`)
- Modules: puntal driver (`bin/puntal_task.sh`, `agent_os/puntal.py`), `agent_os/lib.py` (`TaskClass`,
  `PuntalConfig`), `prompts/puntal.md`, `bench/puntal/`
- Plan: `docs/AGENTOS_V2_PLAN.md`, Phase 0; founding decisions 4 and 6
- Note 2026-10-07 (#112): `agent_os/puntal.py` is now `agent_os/product/puntal.py`; the decision is unchanged.

## Context

Agentos v2 puts a product's interface live before its code exists: every UI action is bound to a use
case, and an action nobody has implemented is answered by a headless agent -- a *puntal* -- reading the
use case and the goals above it. Two founding decisions frame it. Decision 6: puntales run as headless
Claude Code processes with the same launch mechanism as workers. Decision 4: state is real from day
one and behaviour is improvised, because a model improvises behaviour acceptably and stores state
badly, so a puntal without persistence contradicts itself between sessions.

The riskiest hypothesis is that a process per click is fast and cheap enough, and that what the puntal
persists stays coherent across sessions. Phase 0 builds the instrument that tests it. Nothing that
already exists fits as it is: a worker holds a worktree and writes code; a one-shot role (`agent_task.sh`)
detaches, wakes the planner and signs as a GitHub App, none of which a click has any use for; and
`claude -p` by default loads the user's `CLAUDE.md`, rules, memory, skills, plugins, MCP servers and
hooks, tens of thousands of tokens that have nothing to do with the click.

## Decision

1. **A puntal is one `claude -p` process per click**, launched by `bin/puntal_task.sh`, a sibling of
   `worker_task.sh`. The shell half only resolves the interpreter and the host root and stamps the
   click's arrival; the work is `agent_os/puntal.py`, so that a click pays for one Python start-up and
   so that stream parsing, the cuts and the telemetry are testable in-process. It does not detach, does
   not mint an identity, does not write a planner event: its caller waits for the answer on stdout,
   which is the response and nothing else, with the exit status saying how the run ended.

2. **It has its own budget class and its own `runs.tsv`.** `TaskClass.role` gains `puntal`
   (`classes.puntal`); a puntal class may not declare `fallback:`, because it confines the backend with
   the flags of one CLI dialect and substitutes nothing -- a click that cannot be answered fails fast.
   The class's three ceilings bind ONE invocation. `max_context` and `max_total_tokens` are checked on
   the live stream and cut the run; `max_cost_usd` is also handed to the CLI (`--max-budget-usd`); a
   `puntal.max_tool_calls` loop guard cuts a run with no commits to count. `puntal.timeout_seconds` is
   a hard wall-clock kill of the process group, **a safety for a hung process and not a budget**
   (`2026-09-14-agent-spend-is-tokens-not-time-and-needs-a-written-budget.md` stands: spend is tokens
   and dollars). Its rows go to `.cache/puntal/runs.tsv` through the helper every role uses, with the
   same five columns. The per-run log carries the `backend:` header, so the guard reads a puntal run as
   one more quota observation; the role is not in `ONE_SHOT_ROLES` and leaves no PID file.

3. **State goes through the app's persistence API, and a puntal without one does not run.** The API is
   a command (`puntal.persistence_command`); the driver writes a shim, `./state`, into the run's empty
   scratch directory that runs it from the host's root, and `./state` is the one thing the puntal's
   tool may run. No command, no run: founding decision 4.

4. **"The puntal never writes code" is enforced mechanically, in layers, and recorded.** (a)
   Availability: `--tools=Bash` removes every other built-in from the model's context. (b) Permission:
   `--permission-mode dontAsk` with the single allow rule `Bash(./state *)`. (c) Audit: every `tool_use`
   is checked as its block closes -- Bash, `./state`, no shell operator, no substitution, one line -- and
   the first violation SIGTERMs the process group (`contract_violation`). (d) Record: every tool call,
   violation, leftover scratch file and CLI permission denial is in the telemetry, and the bench's
   summary turns it into a verdict. The honest limit: Claude Code auto-approves read-only Bash commands
   regardless of rules, so one `cat` may run before layer (c) cuts the run.

5. **The context is contained with `--safe-mode`, `--system-prompt`, `--tools` and an empty scratch
   directory.** `--safe-mode` keeps CLAUDE.md, rules, skills, plugins, hooks, MCP servers, custom
   agents and auto memory out and still authenticates with a subscription login; `--system-prompt`
   replaces Claude Code's prompt with the contract; the scratch directory has no project files. The
   per-call text is ours: the contract (`prompts/puntal.md`, host tokens and one extension point only)
   is the system prompt, and the brief -- node slice, action, payload, state -- is assembled in code
   rather than rendered from the template, because the payload is a person's text and placeholder
   substitution would let it rewrite the brief.

6. **The telemetry record is a contract.** One JSON line per invocation, whatever its outcome, with a
   `schema` version and the fields documented in `docs/AGENT_OS.md` §4.7 (a test holds the code and the
   table to the same list). Latencies run from the click's arrival at the shell driver. The
   **time-to-first-signal is the first assistant text delta of any message**; the first stream line,
   the first message, the first tool call and the first delta of the answer's own message are recorded
   apart, so a narrating model is not mistaken for a fast one.

7. **A gap note is the last line of the final message starting `GAP:`.** The driver strips it from the
   response and records it in `gap_note`. It costs no tool call (a dedicated call would add a round
   trip to the latency being measured) and needs no JSON escaping from the model.

8. **The measurement is a script outside pytest, with its cap in code.** `bench/puntal/measure.py`
   makes real calls only with `--allow-real-calls`, never under pytest, and counts each in a persistent
   per-user file *before* making it; `REAL_CALL_CAP = 30` is a constant and a stage that does not fit in
   what remains is refused whole. A dry run runs the same code against a fake `claude` that emits the
   real stream shapes and never touches the counter. The bench lives at `bench/puntal/`, outside the
   `agent_os` package and so outside the wheel: it is an instrument with toy data, not mechanism, and
   nothing imports it. Hosts that take the subtree receive inert files.

## Rejected

- **An MCP server exposing the persistence API as the only tool.** Structurally stronger -- with
  `--tools=` empty the model would have no Bash at all -- but `--safe-mode` drops every MCP server that
  is not SDK-hosted (read in the CLI's own source, v2.1.289), and without it the user's plugins,
  connectors and hooks come back into the context. Revisit if the spike shows the read-only hole
  matters, together with the cost of one more process per click.
- **`--bare`**, the CLI's other minimal mode: it authenticates with `ANTHROPIC_API_KEY` only and never
  reads OAuth or the keychain, so it cannot run on a subscription login.
- **A broader Bash allow rule, or none, with the prompt asking for restraint.** A prompt is a request;
  the audit and the cut are what make the constraint checkable.
- **The launch gate and fallback of the other roles.** A fallback backend would need another CLI's
  confinement flags; until one exists, a puntal on an exhausted backend fails fast.

## Consequences

- A host that runs no puntal changes nothing: the `puntal:` section and `classes.puntal` are optional
  and a config that predates them still loads. The example config carries both, with placeholder
  numbers.
- The guard sees puntal runs as role runs for quota purposes. A puntal that hits the rate-limit wall
  moves the backend's verdict, as the validator would.
- What a no-go means is the plan's: the spike's report names the design to try next -- a live session
  per user session instead of process-per-click, precomputation, or batched puntales -- and this
  decision is reviewed against those numbers.
- Not decided here: how a node slice is produced (Phase 1), what the refiner does with the telemetry
  (Phase 4), and whether the ceilings and `timeout_seconds` stay at their placeholder values.
