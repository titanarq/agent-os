---
id: dec-state-real-behavior-improvisable
type: decision
title: State real from day one, behavior improvisable
state: in-force
decided: 2026-10-04
sources:
  - "docs/AGENTOS_V2_PLAN.md, 'Founding decisions' row 4 and 'Phase 0'; approved by the owner in the design discussion of 2026-10-04"
premises:
  - "LLMs improvise behavior acceptably and consistent storage badly"
  - "A puntal without persistence contradicts itself between sessions"
rejected_alternatives:
  - option: "A stateless improvised puntal: behavior and state both improvised, nothing persisted"
    reason: "The second premise argues it: a puntal without persistence contradicts itself between sessions"
    basis: stated
review_triggers:
  - "Phase 0 evidence contradicts it"
---
The state a puntal answers from is real from day one: it is read and written through the app's
persistence API, so it is consistent across sessions whether the behavior on top of it is improvised
or built. The behavior may be improvised by a puntal; the storage is never left to improvisation.
