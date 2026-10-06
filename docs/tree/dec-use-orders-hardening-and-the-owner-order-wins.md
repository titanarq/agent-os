---
id: dec-use-orders-hardening-and-the-owner-order-wins
type: decision
title: Use orders what is consolidated next, and the owner's order wins
state: in-force
decided: '2026-10-06'
sources:
- Owner design discussion of 2026-10-06, how pass, level 3, goal A (a usable product early, grown by real use)
- Owner design discussion of 2026-10-05, point 1, and point 2 (the progress board orders the backlog)
premises:
- What the owner uses most is what matters first; a plan written before use guesses it
- The owner may know an order use cannot show yet
rejected_alternatives:
- option: Order the backlog by a plan written in advance
  reason: It is the over-specification the first goal rejects
  basis: stated
review_triggers:
- The owner reorders by hand most of what use proposes
---
Each action's priority is its frequency times what its puntal costs -- money, suffered latency and
errors -- as telemetry and the owner's feedback measure it. The owner's order on the progress board
wins over it. The refiner turns the top of that order into tickets.
