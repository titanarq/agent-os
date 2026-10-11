# A stage exit that reads a quota refusal records it as the backend's verdict

- Date: 2026-10-09
- Status: accepted
- Modules: `agent_os/guard.py` (`record_quota_observation`), `agent_os/product/tracker/quota_verdict.py`, `bin/worker_task.sh` (`stage-exit`)
- Plan: `docs/AGENTOS_V2_PLAN.md`, Stage 1; `docs/adr/2026-09-14-quota-exhaustion-is-read-from-the-backend-not-claimed-by-the-agent.md`

## Context
The guard persists a backend's quota verdict (`.cache/agent_guard_<backend>.json`) from a live worker's
tick and from the logs role runs leave, and every launch reads it with a TTL: a worker class or a role that
declares a `fallback:` is routed to it while the verdict is fresh and `exhausted`. A worker relaunched into
an exhausted window dies before its first event, and no tick sees it: the only reader of its refusal is
`stage-exit`, which cut the run as `reason=quota` and wrote nothing else. The next launch -- the planner's
own, a validator's, a relaunch -- read a stale `allowed` and ran into the same wall to find out again.

## Decision
`stage-exit` records `exhausted` in the backend's verdict file whenever it reads a refusal (a stream's
rejected rate-limit event, or the words a run printed instead of events). It goes through the one function
that already writes that file for the role logs, so the lock, the "newer wins" rule and the carried-over
stall bookkeeping are the same. Only a refusal is recorded: a clean exit is no evidence the window is open.

## Consequences
- The verdict lapses by the reader's TTL (`mechanism.quota_verdict_ttl_minutes`); nothing here guesses when
  the window reopens.
- The write never blocks on the lock and never fails the cut: a verdict not written costs one more probe.
- A worker class with no `fallback:` is still launched over an exhausted verdict, as before; refusing it
  (parking workers while the quota is out) is a separate decision and not taken here.
