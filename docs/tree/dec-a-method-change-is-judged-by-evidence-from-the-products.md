---
id: dec-a-method-change-is-judged-by-evidence-from-the-products
type: decision
title: A method change is judged by evidence from the products, and misses become battery cases
state: in-force
decided: '2026-10-06'
sources:
- Owner design discussion of 2026-10-06, how pass, level 3, goal D (Agentos improves with every product)
- Owner design discussion of 2026-10-05/06, points 5 and 6, and the clarification that the vector is not Agentos's own development
premises:
- An agent does not learn; what improves is the method -- prompts, rules, context, code
- 'Nobody grades itself: a method allowed to judge itself learns to hide its errors'
- Evidence from Agentos's own development would make the improvement circular
rejected_alternatives:
- option: An agent rewrites its own prompt from its own evaluation of its errors
  reason: It could learn to make its errors invisible; the failing role may contribute its view, but a test independent of it decides
  basis: stated
- option: Adopt a method change and only watch the telemetry
  reason: The owner accepted a replay battery before adoption, with no fixed cap on its cost, adjusted as it goes
  basis: stated
review_triggers:
- The battery passes a change that then regresses in production
- The battery's cost stops paying for what it catches
---
Judgments taken without the owner are recorded from day one with their later outcomes, which come
from outside: the owner's verdicts and reclaims, reverts, real spend, escaped defects. A method
problem is one that recurs in two branches or more. The consolidator (Opus) proposes a change, with
the failing role's own account as one input; a replay battery of past real cases, the misses
included, decides: the change must get the misses right without breaking what was right. A change of
how is then adopted automatically, every record is stamped with the method version, and a regression
rolls it back automatically; a change of what, or of the evaluator, is the owner's. Proposals are
reviewed in question sessions. A successor model runs the battery once.
