# The v2 subsystems live under `agent_os/product/`; the package root stays for the v1 substrate

- Date: 2026-10-07
- Status: accepted
- Modules: `agent_os/product/` (`tree/`, `puntal.py`), `tests/product/`
- Plan: `docs/AGENTOS_V2_PLAN.md`, Stage 1; issue #112

## Context
The quality ratchet (`docs/tree/dec-every-pull-request-gets-a-code-quality-review.md`) caps a folder
at 12 tracked entries. `agent_os/` already held 12 and `tests/` 34, while Stage 1 adds several
subsystems (quality checks, records, question sessions, a progress board). Without a decision on
where they go, each would land flat in the root or in whichever package happened to have room.

## Decision
1. Everything that works on a host's product -- its tree, its puntals and, later, its records,
   question sessions and progress board -- lives under `agent_os/product/`, one subpackage or module
   per subsystem. Their tests mirror that under `tests/product/<subsystem>/`.
2. The package root keeps the v1 substrate (`guard`, `lib`, `issues`, `install`, `doctor`, `render`,
   `cli`...) and the repository-wide checks (`tests/test_no_host_literals.py` and the like).
3. The first move is mechanical (`git mv`, no behaviour change): `agent_os/tree/` to
   `agent_os/product/tree/` and `agent_os/puntal.py` to `agent_os/product/puntal.py`. The console
   script `agent-os-tree` and the driver `bin/puntal_task.sh` keep their names; only the module they
   reach changed (`agent_os.product.tree`, `agent_os.product.puntal`).

## Consequences
- Hosts that pull the subtree get the new paths with the next `git subtree pull`; a host that
  imported `agent_os.tree` or `agent_os.puntal` directly must update the import.
- Earlier ADRs keep their decision text; where they name a moved path they carry a dated note.
