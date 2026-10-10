- Haiku 5.5 for puntals and mechanical tasks (agent-os#161; branch `fix/161-haiku-puntal-override`) -- the owner, 2026-10-10:
  "Cambiar Sonet 5.5 por Haiku 5.5 (no 4.5) para tareas sencillas y para puntales". `config.example.yaml`: the `puntal` and
  `interpreter` classes run on `claude-haiku-5-5`; new worker class `mechanical-haiku` (the default for a small, fully
  specified change, and `tree.ticket_budget_class`); `mechanical-sonnet` keeps working for the issues that name it. New
  `puntal.action_models: {action: model}` lets one action run on a stronger model than the class's (`--model` outranks
  it; the telemetry's `model` and `versions.model` record the effective one). Planner, validator, complex worker and
  expert stay on Sonnet; refiner and task writing do not change. ADR 2026-10-10 amends the one of 2026-09-29.
