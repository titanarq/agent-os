# The app's commands of a puntal click learn the actor from one environment variable

- Date: 2026-10-08
- Status: accepted
- Modules: `agent_os/product/puntal/fast/actor.py`, `json_api.py`, `invocation.py`, `turn.py`,
  `stream/launch.py`
- Plan: `docs/AGENTOS_V2_PLAN.md`, Stage 1; `docs/tree/dec-a-puntal-plans-in-one-turn-and-code-executes.md`

## Context
The pre-helper's reads, the executor and the slow path's `./state` are the app's own commands, run by
the driver for one person's click. Neither the plan nor the operations say who that person is, and the
puntal must not be the one to say it: derived and identifying data is the app's
(`dec-a-puntal-plans-in-one-turn-and-code-executes`, part 3). What a host's shell exported reached
those commands by inheritance, which no document promised.

## Decision
One environment variable, `PUNTAL_ACTOR`, named after the others the driver owns (`PUNTAL_*`). The
`--json` request's `actor` (text, no NUL) sets it for the reads, the executor and the slow path's
shim; without one, what the caller exported is passed on unchanged; without that it is not set, and the
driver never invents an actor. The slow path's shim exports it itself, because whether the backend's
own Bash tool passes the environment on is not the driver's to rely on. The brief does not carry it, so
the model never sees it, and the telemetry does not record it.

## Consequences
- The operations' shape and the host's configured command lines do not change; a command in any
  language reads one variable.
- An app that wants `created_by` stamps it in its executor, from the variable.
- Not decided here: whether the actor should enter the brief (a puntal that answers "my tickets") or
  the telemetry (who a verdict was about). Both need an owner's call on what the model and the logs may
  hold about a person.
