---
id: dec-the-cycle-applies-at-every-scale
type: decision
title: Agentos's cycle applies at every scale, Agentos itself included
state: in-force
decided: 2026-10-06
sources:
  - "Owner design discussion of 2026-10-06, on the decomposition of the puntal's work: 'first the goal and the use cases, then the agents that prop them up, and little by little the use case is refined, turning those agents into deterministic implementation'"
premises:
  - "In Phase 0, four of the five model turns of the slowest puntal action were mechanical bookkeeping and one was judgment; the cycle that hardens a product is what fixed it"
  - "An agent's step that has become mechanical costs a model turn every time it runs, and code does it in milliseconds"
rejected_alternatives:
  - option: "Design the puntal, and every other mechanism of Agentos, as a fixed component specified upfront"
    reason: "Implied by the owner's statement, not argued at approval: a mechanism designed upfront is the over-specification the first goal rejects, and it cannot improve from evidence"
    basis: implied
review_triggers:
  - "Turning an agent's step into code makes an action worse more than once (more rigid, or slower to change when the owner's needs change)"
---
The cycle that defines Agentos -- first the goal and the use cases, then agents that prop them up,
then, little by little, the use case refined and those agents turned into deterministic
implementation -- applies at every scale: to a product's use case, to a single action of a puntal
(its mechanical steps become code helpers while its judgment stays a model call), and to Agentos's
own mechanisms. Hardening is not all or nothing: an action can be hardened step by step. Every
mechanism written this way is a how, so it stays improvable from evidence like the rest.
