---
id: fr-agentos-instructions-do-not-contradict-each-other
type: functional-requirement
title: The instructions of Agentos and of its agents do not contradict each other
parent: goal-efficient-with-what-it-spends
sources:
- 'Owner, 2026-10-10, before attending a request in a test session («antes de antenderlo quiero que repases 3 puntos»), point 1: «Mejora de instrucciones de agentos»; «Chequear incoherencias e inconsistencias en todo agentos incluyendo sus agentes.»'
decisions:
- dec-a-method-change-is-judged-by-evidence-from-the-products
mechanism: pending
---
The instructions that steer Agentos -- its agent definitions, role prompts, project rules and the
documents they point to -- and the instructions of each agent it runs are checked for
incoherences and inconsistencies across the whole, agents included. Two instructions that disagree
cost a run in reconciling them or work done again after the agent obeyed the wrong one, which is why
this sits under efficiency. Which instructions are checked, how often and by whom is the mechanism,
and it is left to the first agent that builds it. A fix to an instruction is a method change and is
judged by evidence from the products (dec-a-method-change-is-judged-by-evidence-from-the-products).
