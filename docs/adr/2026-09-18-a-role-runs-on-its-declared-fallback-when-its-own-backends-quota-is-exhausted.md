# A role runs on its declared fallback when its own backend's quota is exhausted

- Date: 2026-09-18
- Status: accepted
- Modules: workers
- Amends `2026-09-16-workers-run-on-qwen-and-claude-only-reviews.md` (amended, not superseded)

## Context
The 2026-09-16 ADR kept Claude for the three roles that review and plan, and left
`qwen_fallback_eligible` inert everywhere: with every worker on Qwen, no run could hit a Claude
quota wall. The roles could. On 2026-09-18 the planner's 08:48:46Z run was rejected by Claude's
five-hour rate limit in 497 ms and one turn (`.cache/planner/20260918T084846Z.log`,
`terminal_reason: api_error`, `total_cost_usd` 0); seven issues sat `status:ready` (#424, #423,
#422, #421, #419, #417, #402) with no worker alive and a Qwen allowance free until 2026-09-20. The
only route off an exhausted Claude quota was the planner redispatching a worker, and the planner is
itself a Claude role, so the mechanism stopped with work to do and capacity unused.

## Decision
Each of the three role classes may declare a `fallback:` in `config/agents.yaml` (backend, model,
and which of its ceilings bind the substituted run), and the launch of each role reads the guard's
own persisted verdict (`.cache/agent_guard_<backend>.json`, `last_quota_status`) before spending a
turn: `exhausted` inside `mechanism.quota_verdict_ttl_minutes` plus a declared fallback runs the
fallback; anything else — `allowed`, unknown, stale, or exhausted with nothing declared — runs the
class's own backend. The verdict is never an agent's claim about its own quota
(`2026-09-14-quota-exhaustion-is-read-from-the-backend-not-claimed-by-the-agent.md`). The guard's
cut is unchanged and its `quota_exhausted_no_fallback` page now fires only for a class that declares
no way round the window.

**A review produced by the fallback counts as the validator's approval for the merge gate** (the
human's decision of 2026-09-18): the gate reads a review authored by the App the validator signs
as, and that App comes from `project.role_apps`, never from the backend that ran; the independence
the gate rests on is the validator never being the PR's author, which a substitution does not touch.

The substitution must not lose the record of itself — the review body's first line, the log's
identity lines, the `runs.tsv` model column and the `<role>_finished` event all name the backend
that ran.

## Consequences
An exhausted Claude window stops nothing that names a way round it. A weaker model may write a
review, a refinement or a plan, and each says so where a reader will see it; spend accounting keeps
Claude in USD and Qwen in tokens because the row carries the model that ran. A stale verdict
deliberately costs a refused start rather than a substituted review: the TTL is 60 minutes and
unknown launches Claude.

Known limit, written in `docs/modules/workers.md` *Traps*: the guard only observes a **worker's**
stream, so with no Claude worker running there is no verdict on disk and roles launch on Claude — a
role's own rejection teaches the gate nothing. Closing that gap needs a decision about who else may
write the guard's bookkeeping, and is a separate issue.

Nothing raises `planner.max_parallel_issues` (#374), nothing calibrates the Qwen ceilings (#342),
and nothing reads a quota signal out of Qwen's stream, which carries none.

## Source
Decided by the human on 2026-09-18, issue #425.
