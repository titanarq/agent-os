---
id: dec-a-soft-product-decision-is-the-refiners-and-a-hard-one-the-owners
type: decision
title: The refiner revises a soft product decision; the owner revises a hard one
state: in-force
decided: '2026-10-06'
sources:
- Owner design discussion of 2026-10-06, how pass, level 3, goal C (the owner decides what; Agentos decides how)
- Owner design discussion of 2026-10-05, point 1, question 3
premises:
- A product decision with nothing built on it is cheap to change
- 'Hardness is derived, not declared: the number of implemented or hardened nodes whose slice includes the decision'
rejected_alternatives:
- option: The owner revises every product decision
  reason: The owner chose that soft ones are the refiner's, with a record
  basis: stated
- option: Hardness declared by hand
  reason: The owner chose to start with derived hardness
  basis: stated
review_triggers:
- The owner reverses, more than once, a soft decision the refiner revised
---
A product decision's hardness is the number of implemented or hardened nodes whose slice includes
it. A soft one (none, or below a configured threshold) is revised by the refiner, with a record the
owner sees in the next question session; a hard one goes to the owner. This applies to product
decisions in a host's tree; a decision of Agentos's own method follows the what/how rule.
