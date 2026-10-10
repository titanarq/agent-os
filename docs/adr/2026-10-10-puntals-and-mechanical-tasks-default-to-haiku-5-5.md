# Puntals, the interpreter and mechanical tasks default to Haiku 5.5; one action may name its own model

- Date: 2026-10-10
- Status: accepted
- Modules: `config.example.yaml`, `agent_os/product/config.py`, `agent_os/product/puntal/options.py`
- Amends: `2026-09-29-claude-roles-default-to-sonnet-5-5-and-agent-models-are-config.md` (decision 2:
  "everything on Claude defaults to Sonnet 5.5")
- Issue: agent-os#161
- Tree: `docs/tree/dec-a-puntal-plans-in-one-turn-and-code-executes.md`,
  `docs/tree/dec-a-method-change-is-judged-by-evidence-from-the-products.md`,
  `docs/tree/dec-one-backend-claude-code-with-opus-at-the-top.md`, `docs/tree/dec-v2-wraps-v1.md`

## Context
The owner, 2026-10-10: "Cambiar Sonet 5.5 por Haiku 5.5 (no 4.5) para tareas sencillas y para
puntales" (`claude-haiku-5-5`). A puntal plans in one turn with no tool and code executes the plan
(`dec-a-puntal-plans-in-one-turn-and-code-executes`), so what the model contributes is small and the
click waits for it: latency and cost per click are the quantities that matter.

An experiment of 2026-10-10 ran a host's real actions on both models, 60 runs for 0.50 USD. Haiku
returned a valid plan every time (100 %), had the same effect as Sonnet on 8 of the 10 actions,
answered in a median of 2.96 s against 6.67 s and cost about 30 times less. It failed on 3 actions of
that host, each time in its own way: it wrote a field the schema does not have, it left an answer
incomplete, and it asserted a state it had no data for.

The experiment measured puntal actions. Mechanical worker tasks are Haiku's by the owner's decision,
not by a measurement of its own.

## Decision
1. **Defaults.** In `config.example.yaml` the `puntal` and `interpreter` classes run on
   `claude-haiku-5-5`. A new worker class `mechanical-haiku` (the same ceilings as
   `mechanical-sonnet`) is the default for a small, fully specified change; `tree.ticket_budget_class`
   names it. The class descriptions tell the refiner which one a new task takes.
2. **What stays on Sonnet.** The planner, the validator, the complex worker (`complex-sonnet`) and the
   expert. The refiner and task writing do not change (the refiner is on Sonnet since the amendment of
   2026-10-06, task writing is `project.agent_models.task_writer`). The custodian and the
   consolidator stay on Opus. `mechanical-sonnet` keeps existing and working: an issue that already
   carries `<!-- budget: mechanical-sonnet -->` runs on Sonnet, and a host may name it in any new one.
3. **One action may name its own model.** `puntal.action_models: {action: model}`. The key is the
   request's `action`; an action not named runs on `classes.puntal.model`, and `puntal_task.sh --model`
   outranks both. The telemetry records the effective model (`model`, `versions.model`), so the cost
   and the verdicts of an action are always attributable to the model that answered. Empty by default:
   the mechanism does not name a host's actions, and the three actions Haiku failed are set to Sonnet
   in that host's own `config/agents.yaml`, never in this repository
   (`2026-09-14-the-agent-mechanism-is-project-agnostic-and-configured-not-coded.md`).
4. **The default is a hypothesis the products keep judging.** A failure of Haiku on an action is not a
   reason to move the class back: it is one line in `puntal.action_models`. If an action keeps needing
   it, or most actions do, the evidence is in the telemetry
   (`dec-a-method-change-is-judged-by-evidence-from-the-products`).

## Consequences
- A host that pulls this keeps its own `classes` untouched (the example's values are examples): its
  puntal stays on whatever model it names until it edits `config/agents.yaml`.
- A host that adopts the new defaults names, in `puntal.action_models`, the actions it measured Haiku
  failing, before its puntal class moves.
- `backend_default_model` still answers Sonnet for the claude backend: it reads the first worker class
  of the backend, which stays `mechanical-sonnet`, so a worker dispatched with no class is not put on
  the cheapest model by accident.
- Rejected: moving the whole puntal class back to Sonnet for the three failing actions (it pays
  Sonnet's latency and cost on the others); an allowlist of actions inside the mechanism (a host's
  action names in code).
