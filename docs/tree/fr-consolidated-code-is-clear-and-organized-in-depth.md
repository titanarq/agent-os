---
id: fr-consolidated-code-is-clear-and-organized-in-depth
type: functional-requirement
title: Consolidated code is clear and organized in depth
parent: goal-product-early-grown-by-use
sources:
- 'Owner design discussion of 2026-10-06: a code-quality review in every pull request, from now on'
decisions:
- dec-every-pull-request-gets-a-code-quality-review
mechanism: |-
  Stage 1, in products and in agent-os. Every pull request gets two checks. Deterministic ones in CI,
  as a ratchet -- new files comply and touched ones never get worse -- and blocking: at most a
  configured number of entries per folder and of lines per file (defaults 12 and 300). And a review an
  agent makes of the diff -- SOLID, long self-explanatory names, comments only for a non-obvious why --
  which requests changes the way the validator does.
implementation: 'agent_os/quality/ (agent-os-quality, the CI ratchet; config section `quality:`), prompts/validator.md ("CODE QUALITY OF THE DIFF"), #114'
---
The code that is consolidated follows the SOLID principles, explains itself (long descriptive names
of variables and methods, few comments), is organized in depth (no folder with dozens of files) and
lives in small files, so every agent reads a small piece of it.
