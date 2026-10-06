# Claude roles default to Sonnet 5.5; the refiner and task writing stay on Opus; agent models are config

- Date: 2026-09-29
- Status: accepted
- Modules: install (`agent_os/install.py`, `agent_os/render.py`), `agents/*.md`, `config.example.yaml`
- Issue: agent-os#96

## Context

Anthropic released Claude Sonnet 5.5 (`claude-sonnet-5-5`, alias `sonnet`), nearly as capable as
Opus at a fraction of the cost. Every Claude role of the mechanism ran on Opus, and the choice was
hard-coded in two places a host could not reach: `model: opus` in `agents/control-plane.md`, and
Opus stated as the design in `config.example.yaml` and `docs/AGENT_OS.md`. A per-role switch left
stale text and one non-configurable pin (the generated `.claude/agents/*.md` are overwritten by
every `agent-os-install --force`).

## Decision

1. The `model:` of every agent definition is a `__TOKEN__` rendered from `project.agent_models`
   (`control_plane`, `worker_runner`, `task_writer`), with documented defaults. Model ids stay
   opaque to the mechanism: no allowlist, no price table, cost is what the CLI reports.
2. Everything on Claude defaults to Sonnet 5.5: the control plane, the worker runner, and the
   example config's planner and validator classes.
3. Two roles stay on Opus. The refiner (`claude-opus-5`): splitting and rewriting issues sets the
   quality of everything downstream, and it runs rarely. Task writing: the same reasoning, and the
   duty that produces the briefs workers execute.
4. An agent definition has one model, so the task-writing duty (Duty 1 of the control plane) is its
   own definition, `agents/task-writer.md`, default `opus`. The control plane cannot spawn agents:
   asked to write a task it says the main thread should use `task-writer`.
5. The quota verdict stays per backend, not per model, and this is documented rather than keyed:
   Opus and Sonnet on the `claude` backend share one verdict. A host wanting the families isolated
   declares a second backend.

## Consequences

- A host moves any role's model in `config/agents.yaml`, never in a generated file.
- After a `subtree pull` a host runs `agent-os-install --force`; `task-writer.md` appears in its
  `.claude/agents/`, and its own `classes` are untouched (the example's values are examples).
- `tests/golden/validator.md` records the example config's validator model.
- Rejected: a per-agent `model:` key next to each definition's own file (a host would edit the
  mechanism, against the 2026-09-21 ADR); keying the quota verdict by model (needs a detector that
  can attribute an exhaustion to a family, which the CLI does not report).

## Amendment, 2026-10-06 (Agentos v2)
Opus is kept only for the highest level and in minimal use: the custodian and the consolidator. The
refiner moves to Sonnet, and task writing is mostly replaced by `agent-os-tree compile`
(`docs/tree/dec-one-backend-claude-code-with-opus-at-the-top.md`).
