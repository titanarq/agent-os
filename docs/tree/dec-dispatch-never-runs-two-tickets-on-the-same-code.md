---
id: dec-dispatch-never-runs-two-tickets-on-the-same-code
type: decision
title: Dispatch never runs two tickets on the same code at once, and dependencies go first
state: in-force
decided: '2026-10-06'
sources:
- 'The owner''s original proposal of 2026-10-04 (design discussion that produced docs/AGENTOS_V2_PLAN.md): ''a coordinator agent checks that no two agents touch the same code and decides who starts'''
- Final cross-check of the how pass, approved by the owner on 2026-10-06
premises:
- Slots (#91) give real parallelism on one backend, so two workers can reach the same code
- 'The tree format has no dependency between nodes yet (Phase 1 left every ticket at ''Dependencies: none'')'
rejected_alternatives:
- option: Parallel tickets resolve their conflicts at merge
  reason: 'Implied by the first premise, not argued at approval: a conflict found at merge throws away one of two finished pieces of work'
  basis: implied
review_triggers:
- Two parallel tickets conflict in the same code
---
A node may declare the nodes it depends on (`depends_on:`), and its components and implementation
paths are known. The planner orders tickets by their dependencies and never runs at once two
tickets whose nodes share a component or an implementation path.
